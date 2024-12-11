import logging
import arrow

from ...features import DEFAULT_FEATURES
from ... import features
from ...eventparser.generic import Events, decode_raw_events, EVENT_LEN
from ...eventparser.utils import bitmask_to_list
from ...eventparser import events as eventtypes
from ...domain.tandemsource.event_class import EventClass
from ...parser.nightscout import (
    EXERCISE_EVENTTYPE,
    SLEEP_EVENTTYPE,
    NightscoutEntry
)

NOT_ENDED = "Not Ended"

logger = logging.getLogger(__name__)

class ProcessUserMode:
    def __init__(self, tconnect, nightscout, tconnect_device_id, pretend, features=DEFAULT_FEATURES):
        self.tconnect = tconnect
        self.nightscout = nightscout
        self.tconnect_device_id = tconnect_device_id
        self.pretend = pretend
        self.features = features

    def enabled(self):
        return features.PUMP_EVENTS in self.features

    def process(self, events, time_start, time_end):
        logger.debug("ProcessUserMode: querying for last uploaded exercise entry")
        exercise_last_upload = self.nightscout.last_uploaded_entry(EXERCISE_EVENTTYPE, time_start=time_start, time_end=time_end)
        exercise_last_upload_time = None
        if exercise_last_upload:
            exercise_last_upload_time = arrow.get(exercise_last_upload["created_at"])
        logger.info("ProcessUserMode: Last Nightscout exercise upload: %s" % exercise_last_upload_time)

        exercise_not_ended = False
        if exercise_last_upload and NOT_ENDED in exercise_last_upload.get("reason", ""):
            exercise_not_ended = True
            logger.info("ProcessUserMode: Last exercise not ended: %s" % exercise_last_upload)


        logger.debug("ProcessUserMode: querying for last uploaded sleep entry")
        sleep_last_upload = self.nightscout.last_uploaded_entry(SLEEP_EVENTTYPE, time_start=time_start, time_end=time_end)
        sleep_last_upload_time = None
        if sleep_last_upload:
            sleep_last_upload_time = arrow.get(sleep_last_upload["created_at"])
        logger.info("ProcessUserMode: Last Nightscout sleep upload: %s" % sleep_last_upload_time)

        sleep_not_ended = False
        if sleep_last_upload and NOT_ENDED in sleep_last_upload.get("reason", ""):
            sleep_not_ended = True
            logger.info("ProcessUserMode: Last sleep not ended: %s" % sleep_last_upload)

        last_upload_time = None
        if exercise_last_upload_time and sleep_last_upload_time:
            last_upload_time = max(exercise_last_upload_time, sleep_last_upload_time)
        elif exercise_last_upload_time:
            last_upload_time = exercise_last_upload_time
        elif sleep_last_upload_time:
            last_upload_time = sleep_last_upload_time

        logger.info("ProcessUserMode: Last Nightscout usermode upload: %s" % last_upload_time)


        ns_entries = []

        processed_sleep = []
        processed_exercise = []
        start_sleep = None
        start_exercise = None
        for event in sorted(events, key=lambda x: x.eventTimestamp):
            if last_upload_time and arrow.get(event.eventTimestamp) <= last_upload_time:
                if self.pretend:
                    logger.info("ProcessUserMode: Skipping usermode event not after last upload time: %s (time range: %s - %s)" % (event, time_start, time_end))
                continue

            if self.is_start_sleep(event):
                start_sleep = event
            elif self.is_stop_sleep(event):
                if start_sleep:
                    processed_sleep.append((start_sleep, event))
                    start_sleep = None
                else:
                    if sleep_not_ended:
                        logger.info("ProcessUserMode: Found StopSleep without StartSleep, with incomplete sleep event in nightscout: %s NS: %s" % (event, sleep_last_upload))
                        ns_entries.append(self.process_unended_sleep_stop(event, sleep_last_upload))
                    else:
                        logger.warning("ProcessUserMode: Found StopSleep without StartSleep, and no active sleep event in nightscout: %s" % event)
            elif self.is_start_exercise(event):
                start_exercise = event
            elif self.is_stop_exercise(event):
                if start_exercise:
                    processed_exercise.append((start_exercise, event))
                    start_exercise = None
                else:
                    if exercise_not_ended:
                        logger.info("ProcessUserMode: Found StopExercise without StartExercise, with incomplete exercise event in nightscout: %s NS: %s" % (event, exercise_last_upload))
                        ns_entries.append(self.process_unended_exercise_stop(event, exercise_last_upload))
                    else:
                        logger.warning("ProcessUserMode: Found StopExercise without StartExercise, and no active exercise event in nightscout: %s" % event)
            else:
                logger.warning("ProcessUserMode: not sure how to process event: %s" % event)

        if start_sleep:
            processed_sleep.append((start_sleep, None))
            logger.info("ProcessUserMode: sleep is active")
        if start_exercise:
            processed_exercise.append((start_exercise, None))
            logger.info("ProcessUserMode: exercise is active")

        for items in processed_sleep:
            ns_entries.append(self.sleep_to_nsentry(start=items[0], stop=items[1], time_end=time_end))

        for items in processed_exercise:
            ns_entries.append(self.exercise_to_nsentry(start=items[0], stop=items[1], time_end=time_end))

        return ns_entries

    def write(self, ns_entries):
        count = 0
        for entry in ns_entries:
            if self.pretend:
                logger.info("Would upload to Nightscout: %s" % entry)
            else:
                logger.info("Uploading to Nightscout: %s" % entry)
                self.nightscout.upload_entry(entry)
            count += 1

        return count

    def is_start_sleep(self, event):
        return event.requestedaction == eventtypes.LidAaUserModeChange.RequestedactionEnum.StartSleep
    def is_stop_sleep(self, event):
        return event.requestedaction == eventtypes.LidAaUserModeChange.RequestedactionEnum.StopSleep or \
               event.requestedaction == eventtypes.LidAaUserModeChange.RequestedactionEnum.StopAll
    def is_start_exercise(self, event):
        return event.requestedaction == eventtypes.LidAaUserModeChange.RequestedactionEnum.StartExercise
    def is_stop_exercise(self, event):
        return event.requestedaction == eventtypes.LidAaUserModeChange.RequestedactionEnum.StopExercise or \
               event.requestedaction == eventtypes.LidAaUserModeChange.RequestedactionEnum.StopAll


    def sleep_to_nsentry(self, start, stop=None, time_end=None):
        if start and stop:
            reason = None
            if start.sleepstartedbygui == eventtypes.LidAaUserModeChange.SleepstartedbyguiEnum.TrueVal:
                reason = "Sleep (Manual)"
            elif start.activesleepschedule:
                reason = "Sleep (Scheduled)"

            duration_mins = (stop.eventTimestamp - start.eventTimestamp).seconds / 60
            return NightscoutEntry.activity(
                created_at=start.eventTimestamp.format(),
                reason=reason,
                duration=duration_mins,
                event_type=SLEEP_EVENTTYPE,
                pump_event_id = "%s,%s" % (start.seqNum, stop.seqNum)
            )
        elif start:
            reason = None
            if start.sleepstartedbygui == eventtypes.LidAaUserModeChange.SleepstartedbyguiEnum.TrueVal:
                reason = "Sleep (Manual)"
            elif start.activesleepscheduleRaw:
                reason = "Sleep (Scheduled)"

            duration_mins = (time_end - start.eventTimestamp).seconds / 60
            return NightscoutEntry.activity(
                created_at=start.eventTimestamp.format(),
                reason=reason + " - " + NOT_ENDED if reason else NOT_ENDED,
                duration=duration_mins,
                event_type=SLEEP_EVENTTYPE,
                pump_event_id = "%s" % start.seqNum
            )


    def exercise_to_nsentry(self, start, stop=None, time_end=None):
        if start and stop:
            reason = "Exercise"
            if start.exercisechoice == eventtypes.LidAaUserModeChange.ExercisechoiceEnum.Timed:
                reason = "Exercise (Timed)"

            if stop.exercisestoppedbytimer == eventtypes.LidAaUserModeChange.ExercisestoppedbytimerEnum.TrueVal:
                reason += " (Stopped by timer)"

            duration_mins = (stop.eventTimestamp - start.eventTimestamp).seconds / 60
            return NightscoutEntry.activity(
                created_at=start.eventTimestamp.format(),
                reason=reason,
                duration=duration_mins,
                event_type=EXERCISE_EVENTTYPE,
                pump_event_id = "%s,%s" % (start.seqNum, stop.seqNum)
            )
        elif start:
            reason = "Exercise"
            if start.exercisechoice == eventtypes.LidAaUserModeChange.ExercisechoiceEnum.Timed:
                reason = "Exercise (Timed)"

            duration_mins = (time_end - start.eventTimestamp).seconds / 60
            return NightscoutEntry.activity(
                created_at=start.eventTimestamp.format(),
                reason=reason + " - " + NOT_ENDED,
                duration=duration_mins,
                event_type=EXERCISE_EVENTTYPE,
                pump_event_id = "%s" % start.seqNum
            )

    def process_unended_sleep_stop(self, event, sleep_last_upload):
        logger.info("ProcessUserMode: Deleting old sleep event treatment before pushing update (delete treatments/%s)" % sleep_last_upload["_id"])
        if self.pretend:
            logger.info("ProcessUserMode: Skipping delete in pretend mode")
        else:
            self.nightscout.delete_entry('treatments/%s' % sleep_last_upload["_id"])

        duration_mins = (event.eventTimestamp - arrow.get(sleep_last_upload["created_at"])).seconds / 60
        return NightscoutEntry.activity(
            created_at=sleep_last_upload["created_at"],
            reason=sleep_last_upload["reason"].replace(" - %s" % NOT_ENDED, ""),
            duration=duration_mins,
            event_type=SLEEP_EVENTTYPE,
            pump_event_id="%s,%s" % (sleep_last_upload.get("pump_event_id",""), event.seqNum)
        )

    def process_unended_exercise_stop(self, event, exercise_last_upload):
        logger.info("ProcessUserMode: Deleting old exercise event treatment before pushing update (delete treatments/%s)" % exercise_last_upload["_id"])
        if self.pretend:
            logger.info("ProcessUserMode: Skipping delete in pretend mode")
        else:
            self.nightscout.delete_entry('treatments/%s' % exercise_last_upload["_id"])

        reason = exercise_last_upload["reason"].replace(" - %s" % NOT_ENDED, "")
        if event.exercisestoppedbytimer == eventtypes.LidAaUserModeChange.ExercisestoppedbytimerEnum.TrueVal:
            reason += " (Stopped by timer)"

        duration_mins = (event.eventTimestamp - arrow.get(exercise_last_upload["created_at"])).seconds / 60
        return NightscoutEntry.activity(
            created_at=exercise_last_upload["created_at"],
            reason=reason,
            duration=duration_mins,
            event_type=EXERCISE_EVENTTYPE,
            pump_event_id="%s,%s" % (exercise_last_upload.get("pump_event_id",""), event.seqNum)
        )