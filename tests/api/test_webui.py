#!/usr/bin/env python3

import unittest
import itertools
import datetime
import json

import requests
import requests_mock

from bs4 import BeautifulSoup

from tconnectsync.api.webui import WebUIScraper
from tconnectsync.domain.device_settings import Device, Profile, ProfileSegment

from .fake import ControlIQApi

from tconnectsync.api.controliq import ControlIQApi as RealControlIQApi
from tconnectsync.api.common import ApiException, ApiLoginException, base_headers

class TestWebUIScraper(unittest.TestCase):
    maxDiff = None

    DEVICES_HTML = """
<html xmlns="http://www.w3.org/1999/xhtml">

<head>
</head>

<body>
    <form method="post" action="./My_Devices.aspx" id="form1">
        <div id="content">
            <div style="float: right">
                <a href="../Help/AddBGMeter.aspx">
                    <img src="../images/btn_add_bg_meter.png" border="0" style="padding-bottom: 16px;"
                        alt="Add a Blood Glucose Meter" title="Add a Blood Glucose Meter"></a>
            </div>
            <div class="title">
                My Devices</div>
            <div class="subtext">
                These are the devices that are currently associated with your account.
            </div>

            <!-- Start device chunk -->
            <div class="box">
                <div class="deactivate_div">
                    <a class="deactivate cboxElement"
                        href="DeactivateDevice.aspx?guid=00000000-0000-0000-0000-000000000001&amp;IsPump=True">
                        Deactivate</a> <a
                        href="DeactivateDevice.aspx?guid00000000-0000-0000-0000-000000000001&amp;IsPump=True"
                        class="deactivate cboxElement">
                        <img src="/Images/icon_deactivate.png" align="absmiddle" hspace="6"
                            alt="Deactivate this device"></a>
                </div>
                <div class="subTitle">
                    <!-- START: This is the Device Name Link -->

                    t:slim X2<sup>™</sup> Insulin Pump

                    <!-- END: This is the Device Name Link -->
                </div>
                <div align="center" class="device_imagebox">
                    <img src="../images/device_tslim41.png">
                    <div style="padding-top: 15px; padding-bottom: 15px">
                        <a href="DeviceSettings.aspx?guid=00000000-0000-0000-0000-000000000001"
                            class="buttonSmall"><span>View Settings</span></a>
                    </div>
                </div>

                <!-- END: View Settings icon and text links -->
                <div>
                    <table class="boxtable">
                        <tbody>
                            <tr>
                                <td style="padding: 8px"><strong>Status</strong></td>
                                <td style="padding: 8px">
                                    <span id="lblDeviceStatus" class="status_activated">Activated</span>
                                    —

                                    Dec 30 2021

                                </td>
                            </tr>
                            <tr>
                                <td style="padding: 8px"><strong>Model #</strong></td>
                                <td style="padding: 8px">
                                    001002717
                                </td>
                            </tr>
                            <tr>
                                <td style="padding: 8px"><strong>Serial #</strong></td>
                                <td style="padding: 8px">
                                    100001
                                </td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>
            <!-- ---------------- -->
            <!-- End device chunk -->
            <!-- ---------------- -->

            <!-- Start device chunk -->
            <div class="box">
                <div class="deactivate_div">
                    <a class="deactivate cboxElement"
                        href="DeactivateDevice.aspx?guid=00000000-0000-0000-0000-000000000002&amp;IsPump=True">
                        Deactivate</a> <a
                        href="DeactivateDevice.aspx?guid00000000-0000-0000-0000-000000000002&amp;IsPump=True"
                        class="deactivate cboxElement">
                        <img src="/Images/icon_deactivate.png" align="absmiddle" hspace="6"
                            alt="Deactivate this device"></a>
                </div>
                <div class="subTitle">
                    <!-- START: This is the Device Name Link -->

                    t:slim X2<sup>™</sup> Insulin Pump

                    <!-- END: This is the Device Name Link -->
                </div>
                <div align="center" class="device_imagebox">
                    <img src="../images/device_tslim41.png">
                    <div style="padding-top: 15px; padding-bottom: 15px">
                        <a href="DeviceSettings.aspx?guid=00000000-0000-0000-0000-000000000002"
                            class="buttonSmall"><span>View Settings</span></a>
                    </div>
                </div>

                <!-- END: View Settings icon and text links -->
                <div>
                    <table class="boxtable">
                        <tbody>
                            <tr>
                                <td style="padding: 8px"><strong>Status</strong></td>
                                <td style="padding: 8px">
                                    <span id="lblDeviceStatus" class="status_activated">Activated</span>
                                    —

                                    Oct 26 2021

                                </td>
                            </tr>
                            <tr>
                                <td style="padding: 8px"><strong>Model #</strong></td>
                                <td style="padding: 8px">
                                    001000354
                                </td>
                            </tr>
                            <tr>
                                <td style="padding: 8px"><strong>Serial #</strong></td>
                                <td style="padding: 8px">
                                    10000002
                                </td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>
            <!-- ---------------- -->
            <!-- End device chunk -->
            <!-- ---------------- -->

            <!-- Start device chunk -->
            <div class="box">
                <div class="deactivate_div">
                    <a class="deactivate cboxElement"
                        href="DeactivateDevice.aspx?guid=00000000-0000-0000-0000-000000000003&amp;IsPump=True">
                        Deactivate</a> <a
                        href="DeactivateDevice.aspx?guid00000000-0000-0000-0000-000000000003&amp;IsPump=True"
                        class="deactivate cboxElement">
                        <img src="/Images/icon_deactivate.png" align="absmiddle" hspace="6"
                            alt="Deactivate this device"></a>
                </div>
                <div class="subTitle">
                    <!-- START: This is the Device Name Link -->

                    t:slim X2<sup>™</sup> Insulin Pump

                    <!-- END: This is the Device Name Link -->
                </div>
                <div align="center" class="device_imagebox">
                    <img src="../images/device_tslim41.png">
                    <div style="padding-top: 15px; padding-bottom: 15px">
                        <a href="DeviceSettings.aspx?guid=00000000-0000-0000-0000-000000000003"
                            class="buttonSmall"><span>View Settings</span></a>
                    </div>
                </div>

                <!-- END: View Settings icon and text links -->
                <div>
                    <table class="boxtable">
                        <tbody>
                            <tr>
                                <td style="padding: 8px"><strong>Status</strong></td>
                                <td style="padding: 8px">
                                    <span id="lblDeviceStatus" class="status_activated">Activated</span>
                                    —

                                    Nov 20 2017

                                </td>
                            </tr>
                            <tr>
                                <td style="padding: 8px"><strong>Model #</strong></td>
                                <td style="padding: 8px">
                                    001000096
                                </td>
                            </tr>
                            <tr>
                                <td style="padding: 8px"><strong>Serial #</strong></td>
                                <td style="padding: 8px">
                                    100003
                                </td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>
            <!-- ---------------- -->
            <!-- End device chunk -->
            <!-- ---------------- -->

            <!-- Start device chunk -->
            <div class="box">
                <div class="deactivate_div">
                    <a class="deactivate cboxElement"
                        href="DeactivateDevice.aspx?guid=00000000-0000-0000-0000-000000000004&amp;IsPump=False">
                        Deactivate</a> <a
                        href="DeactivateDevice.aspx?guid00000000-0000-0000-0000-000000000004&amp;IsPump=False"
                        class="deactivate cboxElement">
                        <img src="/Images/icon_deactivate.png" align="absmiddle" hspace="6"
                            alt="Deactivate this device"></a>
                </div>
                <div class="subTitle">
                    <!-- START: This is the Device Name Link -->

                    OneTouch Verio IQ

                    <!-- END: This is the Device Name Link -->
                </div>
                <div align="center" class="device_imagebox">
                    <img src="../images/devices_Verio_IQ_One_Touch.png">
                </div>

                <div>
                    <table class="boxtable">
                        <tbody>
                            <tr>
                                <td style="padding: 8px"><strong>Status</strong></td>
                                <td style="padding: 8px">
                                    <span id="lblDeviceStatus" class="status_activated">Activated</span>
                                    —

                                    Jan 17 2018

                                </td>
                            </tr>
                            <tr>
                                <td style="padding: 8px"><strong>Model #</strong></td>
                                <td style="padding: 8px">
                                    VERIO IQ
                                </td>
                            </tr>
                            <tr>
                                <td style="padding: 8px"><strong>Serial #</strong></td>
                                <td style="padding: 8px">
                                    ABCDEFGH
                                </td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </form>
</body>
</html>
    """

    def test_my_devices(self):
        ciq = ControlIQApi()
        ciq.needs_relogin = lambda: False
        ciq.loginSession = requests.Session()
        ciq.LOGIN_URL = RealControlIQApi.LOGIN_URL
        ciq.login = lambda email, password: True
        webui = WebUIScraper(ciq)

        with requests_mock.Mocker() as m:
            m.get('https://tconnect.tandemdiabetes.com/myaccount/my_devices.aspx',
                request_headers=base_headers(),

                text=self.DEVICES_HTML)

            devices = webui.my_devices()
            self.assertDictEqual(devices, {
                '100001': Device(**{
                    'name': 't:slim X2™ Insulin Pump', 
                    'model_number': '001002717', 
                    'status': 'Activated —  Dec 30 2021', 
                    'guid': '00000000-0000-0000-0000-000000000001'
                }),
                '10000002': Device(**{
                    'name': 't:slim X2™ Insulin Pump', 
                    'model_number': '001000354', 
                    'status': 'Activated —  Oct 26 2021', 
                    'guid': '00000000-0000-0000-0000-000000000002'
                }), 
                '100003': Device(**{
                    'name': 't:slim X2™ Insulin Pump', 
                    'model_number': '001000096', 
                    'status': 'Activated —  Nov 20 2017', 
                    'guid': '00000000-0000-0000-0000-000000000003'
                }), 
                'ABCDEFGH': Device(**{
                    'name': 'OneTouch Verio IQ', 
                    'model_number': 'VERIO IQ', 
                    'status': 'Activated —  Jan 17 2018', 
                    'guid': None
                })})
    
    PUMP_SETTINGS_HTML = """
<!DOCTYPE html
    PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head></head>
<body>
    <form method="post" action="./DeviceSettings.aspx?guid=00000000-0000-0000-0000-000000000001" id="form1">

        <div id="content">
            <div style="padding-bottom: 10px;">
                <a href='/MyAccount/My_Devices.aspx' class="back">&lt; Back to My Devices</a>
            </div>
            <div style="width: 100%; border-bottom: 1px solid #ccc; float: left; margin-bottom: 8px;">
                <div class="title" style="float: left">
                    <span id="lblPumpSettingsPageTitleByDevice">t:slim X2<sup>&trade;</sup> Pump Settings</span>
                </div>
                <div id="subtab" style="float: right; padding-bottom: 0px; margin-bottom: 0px;">
                    <ul style="padding-bottom: 0px; margin-bottom: 0px; visibility:hidden;">
                        <li style="padding-bottom: 0px; margin-bottom: 0px;">
                            <a id="HyperLink1" class="selected_subtab"
                                href="DeviceSettings.aspx?guid=00000000-0000-0000-0000-000000000001"><span>Settings</span></a>
                        </li>

                    </ul>
                    <input type="image" name="ctl00$ContentBody$lbtnSaveReport" id="lbtnSaveReport" title="Save as PDF"
                        src="../Images/save_report.png" />
                </div>
                <div style="clear: both; padding: 0px; margin: 0px;">
                </div>
            </div>


            <div style="clear: both; padding: 0px; margin: 0px;">
            </div>
            <div id="header" style="width: 100%; float: left;" class="subTitle">
                <div style="float: left; padding-top: 15px; height: 25px; width: 440px;">
                    <div style="float: left;">
                        Settings Uploaded:
                    </div>
                    <div style="float: left; padding-left: 8px;">
                        <div class="RadAjaxPanel" id="ctl00_ContentBody_ctl00_ContentBody_lblUploadDatePanel">
                            <span id="lblUploadDate">Jan 09, 2022</span>
                        </div>&nbsp;&nbsp;
                    </div>
                    <div style="float: left; padding-left: 8px;">
                        <div class="RadAjaxPanel" id="ctl00_ContentBody_ctl00_ContentBody_RadComboBox2Panel">
                            <div id="ctl00_ContentBody_RadComboBox2" class="RadComboBox RadComboBox_Default"
                                style="width:100px;white-space:normal;">
                                <table summary="combobox" style="border-width:0;border-collapse:collapse;width:100%">
                                    <tr class="rcbReadOnly">
                                        <td class="rcbInputCell rcbInputCellLeft" style="width:100%;"><input
                                                name="ctl00$ContentBody$RadComboBox2" type="text"
                                                class="rcbInput radPreventDecorate"
                                                id="ctl00_ContentBody_RadComboBox2_Input" value="3:18 pm  PST"
                                                readonly="readonly" /></td>
                                        <td class="rcbArrowCell rcbArrowCellRight"><a
                                                id="ctl00_ContentBody_RadComboBox2_Arrow"
                                                style="overflow: hidden;display: block;position: relative;outline: none;">select</a>
                                        </td>
                                    </tr>
                                </table>
                                <div class="rcbSlide" style="z-index:6000;display:none;">
                                    <div id="ctl00_ContentBody_RadComboBox2_DropDown"
                                        class="RadComboBoxDropDown RadComboBoxDropDown_Default ">
                                        <div class="rcbScroll rcbWidth">
                                            <ul class="rcbList">
                                                <li class="rcbItem">3:18 pm PST</li>
                                                <li class="rcbItem">3:08 pm PST</li>
                                                <li class="rcbItem">2:57 pm PST</li>
                                                <li class="rcbItem">2:44 pm PST</li>
                                                <li class="rcbItem">2:34 pm PST</li>
                                                <li class="rcbItem">2:26 pm PST</li>
                                                <li class="rcbItem">2:16 pm PST</li>
                                                <li class="rcbItem">2:06 pm PST</li>
                                                <li class="rcbItem">1:54 pm PST</li>
                                                <li class="rcbItem">1:44 pm PST</li>
                                                <li class="rcbItem">1:34 pm PST</li>
                                                <li class="rcbItem">1:26 pm PST</li>
                                                <li class="rcbItem">1:16 pm PST</li>
                                                <li class="rcbItem">1:04 pm PST</li>
                                                <li class="rcbItem">12:54 pm PST</li>
                                                <li class="rcbItem">12:44 pm PST</li>
                                                <li class="rcbItem">12:32 pm PST</li>
                                                <li class="rcbItem">12:26 pm PST</li>
                                                <li class="rcbItem">12:16 pm PST</li>
                                                <li class="rcbItem">12:08 pm PST</li>
                                                <li class="rcbItem">11:54 am PST</li>
                                                <li class="rcbItem">11:44 am PST</li>
                                                <li class="rcbItem">11:32 am PST</li>
                                                <li class="rcbItem">11:24 am PST</li>
                                                <li class="rcbItem">11:14 am PST</li>
                                                <li class="rcbItem">11:00 am PST</li>
                                                <li class="rcbItem">10:50 am PST</li>
                                                <li class="rcbItem">10:32 am PST</li>
                                                <li class="rcbItem">10:30 am PST</li>
                                                <li class="rcbItem">10:20 am PST</li>
                                                <li class="rcbItem">10:06 am PST</li>
                                                <li class="rcbItem">9:54 am PST</li>
                                                <li class="rcbItem">9:44 am PST</li>
                                                <li class="rcbItem">9:32 am PST</li>
                                                <li class="rcbItem">9:20 am PST</li>
                                                <li class="rcbItem">9:06 am PST</li>
                                                <li class="rcbItem">8:56 am PST</li>
                                                <li class="rcbItem">8:44 am PST</li>
                                                <li class="rcbItem">8:32 am PST</li>
                                                <li class="rcbItem">8:26 am PST</li>
                                                <li class="rcbItem">8:16 am PST</li>
                                                <li class="rcbItem">8:06 am PST</li>
                                                <li class="rcbItem">7:54 am PST</li>
                                                <li class="rcbItem">7:44 am PST</li>
                                                <li class="rcbItem">7:32 am PST</li>
                                                <li class="rcbItem">7:26 am PST</li>
                                                <li class="rcbItem">7:14 am PST</li>
                                                <li class="rcbItem">7:04 am PST</li>
                                                <li class="rcbItem">6:52 am PST</li>
                                                <li class="rcbItem">6:42 am PST</li>
                                                <li class="rcbItem">6:32 am PST</li>
                                                <li class="rcbItem">6:26 am PST</li>
                                                <li class="rcbItem">6:14 am PST</li>
                                                <li class="rcbItem">6:02 am PST</li>
                                                <li class="rcbItem">5:52 am PST</li>
                                                <li class="rcbItem">5:42 am PST</li>
                                                <li class="rcbItem">5:30 am PST</li>
                                                <li class="rcbItem">5:28 am PST</li>
                                                <li class="rcbItem">5:16 am PST</li>
                                                <li class="rcbItem">5:06 am PST</li>
                                                <li class="rcbItem">4:54 am PST</li>
                                                <li class="rcbItem">4:42 am PST</li>
                                                <li class="rcbItem">4:30 am PST</li>
                                                <li class="rcbItem">4:26 am PST</li>
                                                <li class="rcbItem">4:14 am PST</li>
                                                <li class="rcbItem">4:04 am PST</li>
                                                <li class="rcbItem">3:52 am PST</li>
                                                <li class="rcbItem">3:42 am PST</li>
                                                <li class="rcbItem">3:30 am PST</li>
                                                <li class="rcbItem">3:24 am PST</li>
                                                <li class="rcbItem">3:14 am PST</li>
                                                <li class="rcbItem">3:02 am PST</li>
                                                <li class="rcbItem">2:52 am PST</li>
                                                <li class="rcbItem">2:42 am PST</li>
                                                <li class="rcbItem">2:30 am PST</li>
                                                <li class="rcbItem">2:24 am PST</li>
                                                <li class="rcbItem">2:14 am PST</li>
                                                <li class="rcbItem">2:02 am PST</li>
                                                <li class="rcbItem">1:52 am PST</li>
                                                <li class="rcbItem">1:40 am PST</li>
                                                <li class="rcbItem">1:30 am PST</li>
                                                <li class="rcbItem">1:22 am PST</li>
                                                <li class="rcbItem">1:12 am PST</li>
                                                <li class="rcbItem">1:02 am PST</li>
                                                <li class="rcbItem">12:52 am PST</li>
                                                <li class="rcbItem">12:40 am PST</li>
                                                <li class="rcbItem">12:30 am PST</li>
                                                <li class="rcbItem">12:22 am PST</li>
                                                <li class="rcbItem">12:12 am PST</li>
                                                <li class="rcbItem">12:02 am PST</li>
                                            </ul>
                                        </div>
                                    </div>
                                </div><input id="ctl00_ContentBody_RadComboBox2_ClientState"
                                    name="ctl00_ContentBody_RadComboBox2_ClientState" type="hidden" />
                            </div>
                        </div>
                    </div>
                </div>
                <div style="float: right; width: 420px; padding-top: 10px; overflow: hidden;">
                    <div class="RadAjaxPanel" id="ctl00_ContentBody_ctl00_ContentBody_RadTabStrip2Panel">
                        <div id="ctl00_ContentBody_RadTabStrip2"
                            class="RadTabStrip RadTabStrip_TMSTabs RadTabStripTop_TMSTabs RadTabStripTop"
                            style="width:419px;overflow:hidden;">
                            <div class="rtsLevel rtsLevel1">
                                <ul class="rtsUL">
                                    <li class="rtsLI rtsFirst" style="width:90px;"><a class="rtsLink rtsSelected"
                                            href="#"><span class="rtsOut"><span class="rtsIn"><span class="rtsTxt">Jan
                                                        09, 2022</span></span></span></a></li>
                                    <li class="rtsLI" style="width:90px;"><a class="rtsLink rtsAfter" href="#"><span
                                                class="rtsOut"><span class="rtsIn"><span class="rtsTxt">Jan 08,
                                                        2022</span></span></span></a></li>
                                    <li class="rtsLI" style="width:90px;"><a class="rtsLink" href="#"><span
                                                class="rtsOut"><span class="rtsIn"><span class="rtsTxt">Jan 07,
                                                        2022</span></span></span></a></li>
                                    <li class="rtsLI" style="width:90px;"><a class="rtsLink" href="#"><span
                                                class="rtsOut"><span class="rtsIn"><span class="rtsTxt">Jan 06,
                                                        2022</span></span></span></a></li>
                                    <li class="rtsLI" style="width:90px;"><a class="rtsLink" href="#"><span
                                                class="rtsOut"><span class="rtsIn"><span class="rtsTxt">Jan 05,
                                                        2022</span></span></span></a></li>
                                    <li class="rtsLI" style="width:90px;"><a class="rtsLink" href="#"><span
                                                class="rtsOut"><span class="rtsIn"><span class="rtsTxt">Jan 04,
                                                        2022</span></span></span></a></li>
                                    <li class="rtsLI" style="width:90px;"><a class="rtsLink" href="#"><span
                                                class="rtsOut"><span class="rtsIn"><span class="rtsTxt">Jan 03,
                                                        2022</span></span></span></a></li>
                                    <li class="rtsLI" style="width:90px;"><a class="rtsLink" href="#"><span
                                                class="rtsOut"><span class="rtsIn"><span class="rtsTxt">Jan 02,
                                                        2022</span></span></span></a></li>
                                    <li class="rtsLI" style="width:90px;"><a class="rtsLink" href="#"><span
                                                class="rtsOut"><span class="rtsIn"><span class="rtsTxt">Jan 01,
                                                        2022</span></span></span></a></li>
                                    <li class="rtsLI" style="width:90px;"><a class="rtsLink" href="#"><span
                                                class="rtsOut"><span class="rtsIn"><span class="rtsTxt">Dec 31,
                                                        2021</span></span></span></a></li>
                                    <li class="rtsLI" style="width:90px;"><a class="rtsLink" href="#"><span
                                                class="rtsOut"><span class="rtsIn"><span class="rtsTxt">Dec 30,
                                                        2021</span></span></span></a></li>
                                    <li class="rtsLI" style="width:90px;"><a class="rtsLink" href="#"><span
                                                class="rtsOut"><span class="rtsIn"><span class="rtsTxt">Dec 29,
                                                        2021</span></span></span></a></li>
                                    <li class="rtsLI" style="width:90px;"><a class="rtsLink" href="#"><span
                                                class="rtsOut"><span class="rtsIn"><span class="rtsTxt">Dec 28,
                                                        2021</span></span></span></a></li>
                                    <li class="rtsLI" style="width:90px;"><a class="rtsLink" href="#"><span
                                                class="rtsOut"><span class="rtsIn"><span class="rtsTxt">Dec 27,
                                                        2021</span></span></span></a></li>
                                    <li class="rtsLI" style="width:90px;"><a class="rtsLink" href="#"><span
                                                class="rtsOut"><span class="rtsIn"><span class="rtsTxt">Dec 26,
                                                        2021</span></span></span></a></li>
                                    <li class="rtsLI" style="width:90px;"><a class="rtsLink" href="#"><span
                                                class="rtsOut"><span class="rtsIn"><span class="rtsTxt">Dec 25,
                                                        2021</span></span></span></a></li>
                                    <li class="rtsLI" style="width:90px;"><a class="rtsLink" href="#"><span
                                                class="rtsOut"><span class="rtsIn"><span class="rtsTxt">Dec 24,
                                                        2021</span></span></span></a></li>
                                    <li class="rtsLI" style="width:90px;"><a class="rtsLink" href="#"><span
                                                class="rtsOut"><span class="rtsIn"><span class="rtsTxt">Dec 22,
                                                        2021</span></span></span></a></li>
                                    <li class="rtsLI" style="width:90px;"><a class="rtsLink" href="#"><span
                                                class="rtsOut"><span class="rtsIn"><span class="rtsTxt">Dec 21,
                                                        2021</span></span></span></a></li>
                                    <li class="rtsLI" style="width:90px;"><a class="rtsLink" href="#"><span
                                                class="rtsOut"><span class="rtsIn"><span class="rtsTxt">Dec 20,
                                                        2021</span></span></span></a></li>
                                    <li class="rtsLI" style="width:90px;"><a class="rtsLink" href="#"><span
                                                class="rtsOut"><span class="rtsIn"><span class="rtsTxt">Dec 19,
                                                        2021</span></span></span></a></li>
                                    <li class="rtsLI" style="width:90px;"><a class="rtsLink" href="#"><span
                                                class="rtsOut"><span class="rtsIn"><span class="rtsTxt">Dec 18,
                                                        2021</span></span></span></a></li>
                                    <li class="rtsLI" style="width:90px;"><a class="rtsLink" href="#"><span
                                                class="rtsOut"><span class="rtsIn"><span class="rtsTxt">Dec 17,
                                                        2021</span></span></span></a></li>
                                    <li class="rtsLI" style="width:90px;"><a class="rtsLink" href="#"><span
                                                class="rtsOut"><span class="rtsIn"><span class="rtsTxt">Dec 16,
                                                        2021</span></span></span></a></li>
                                    <li class="rtsLI" style="width:90px;"><a class="rtsLink" href="#"><span
                                                class="rtsOut"><span class="rtsIn"><span class="rtsTxt">Dec 15,
                                                        2021</span></span></span></a></li>
                                    <li class="rtsLI" style="width:90px;"><a class="rtsLink" href="#"><span
                                                class="rtsOut"><span class="rtsIn"><span class="rtsTxt">Dec 14,
                                                        2021</span></span></span></a></li>
                                    <li class="rtsLI" style="width:90px;"><a class="rtsLink" href="#"><span
                                                class="rtsOut"><span class="rtsIn"><span class="rtsTxt">Dec 13,
                                                        2021</span></span></span></a></li>
                                    <li class="rtsLI" style="width:90px;"><a class="rtsLink" href="#"><span
                                                class="rtsOut"><span class="rtsIn"><span class="rtsTxt">Dec 12,
                                                        2021</span></span></span></a></li>
                                    <li class="rtsLI" style="width:90px;"><a class="rtsLink" href="#"><span
                                                class="rtsOut"><span class="rtsIn"><span class="rtsTxt">Dec 11,
                                                        2021</span></span></span></a></li>
                                    <li class="rtsLI" style="width:90px;"><a class="rtsLink" href="#"><span
                                                class="rtsOut"><span class="rtsIn"><span class="rtsTxt">Dec 10,
                                                        2021</span></span></span></a></li>
                                    <li class="rtsLI" style="width:90px;"><a class="rtsLink" href="#"><span
                                                class="rtsOut"><span class="rtsIn"><span class="rtsTxt">Dec 09,
                                                        2021</span></span></span></a></li>
                                    <li class="rtsLI" style="width:90px;"><a class="rtsLink" href="#"><span
                                                class="rtsOut"><span class="rtsIn"><span class="rtsTxt">Dec 08,
                                                        2021</span></span></span></a></li>
                                    <li class="rtsLI" style="width:90px;"><a class="rtsLink" href="#"><span
                                                class="rtsOut"><span class="rtsIn"><span class="rtsTxt">Dec 07,
                                                        2021</span></span></span></a></li>
                                    <li class="rtsLI" style="width:90px;"><a class="rtsLink" href="#"><span
                                                class="rtsOut"><span class="rtsIn"><span class="rtsTxt">Dec 06,
                                                        2021</span></span></span></a></li>
                                    <li class="rtsLI" style="width:90px;"><a class="rtsLink" href="#"><span
                                                class="rtsOut"><span class="rtsIn"><span class="rtsTxt">Dec 05,
                                                        2021</span></span></span></a></li>
                                    <li class="rtsLI rtsLast" style="width:90px;"><a class="rtsLink" href="#"><span
                                                class="rtsOut"><span class="rtsIn"><span class="rtsTxt">Dec 04,
                                                        2021</span></span></span></a></li>
                                </ul>
                            </div><input id="ctl00_ContentBody_RadTabStrip2_ClientState"
                                name="ctl00_ContentBody_RadTabStrip2_ClientState" type="hidden" />
                        </div>
                    </div>

                    <div style="clear: both; height: 5px;">
                    </div>
                </div>
                <div style="clear: both;">
                </div>
            </div>
            <div style="clear: both;">
            </div>
            <div class="RadAjaxPanel" id="ctl00_ContentBody_ctl00_ContentBody_divXMLPanel">
                <div id="divXML">
                    <?xml version="1.0" encoding="utf-8"?>
                    <div class="top-margin-10">
                        <table width="100%" border="0" cellpadding="8" cellspacing="0" class="settingstable">
                            <tr>
                                <td colspan="3" class="settings_bg borderbottom">
                                    <div class="setting_title">A</div><span class="setting_bg"> Profile</span>
                                </td>
                                <td colspan="2" class="settings_bg borderbottom" align="right" nowrap="nowrap">
                                    <strong>Active at the time of upload</strong>
                                </td>
                            </tr>
                            <tr>
                                <td width="20%" class="settings_bg_sub borderbottom"><strong>Start Time</strong></td>
                                <td width="20%" align="right" class="settings_bg_sub borderbottom"><strong>Basal
                                        Rate</strong></td>
                                <td width="20%" align="right" class="settings_bg_sub borderbottom"><strong>Correction
                                        Factor</strong></td>
                                <td width="20%" align="right" class="settings_bg_sub borderbottom"><strong>Carb
                                        Ratio</strong></td>
                                <td width="20%" align="right" class="settings_bg_sub borderbottom"><strong>Target
                                        BG</strong></td>
                            </tr>
                            <tr>
                                <td class="dottedBottom"><strong>Midnight</strong></td>
                                <td align="right" class="dottedBottom">0.800 u/hr</td>
                                <td align="right" class="dottedBottom">1u:30 mg/dL</td>
                                <td align="right" class="dottedBottom">1u:6.0 g</td>
                                <td align="right" class="dottedBottom">110 mg/dL</td>
                            </tr>
                            <tr>
                                <td class="dottedBottom"><strong>6:00 AM</strong></td>
                                <td align="right" class="dottedBottom">1.250 u/hr</td>
                                <td align="right" class="dottedBottom">1u:30 mg/dL</td>
                                <td align="right" class="dottedBottom">1u:6.0 g</td>
                                <td align="right" class="dottedBottom">110 mg/dL</td>
                            </tr>
                            <tr>
                                <td class="dottedBottom"><strong>11:00 AM</strong></td>
                                <td align="right" class="dottedBottom">1.000 u/hr</td>
                                <td align="right" class="dottedBottom">1u:30 mg/dL</td>
                                <td align="right" class="dottedBottom">1u:6.0 g</td>
                                <td align="right" class="dottedBottom">110 mg/dL</td>
                            </tr>
                            <tr>
                                <td class="dottedBottom"><strong>Noon</strong></td>
                                <td align="right" class="dottedBottom">0.800 u/hr</td>
                                <td align="right" class="dottedBottom">1u:30 mg/dL</td>
                                <td align="right" class="dottedBottom">1u:6.0 g</td>
                                <td align="right" class="dottedBottom">110 mg/dL</td>
                            </tr>
                            <tr>
                                <td class="dottedBottom"><strong>Calculated Total Daily Basal</strong></td>
                                <td align="right" class="dottedBottom">21.65 units</td>
                                <td align="right" class="dottedBottom"> </td>
                                <td align="right" class="dottedBottom"> </td>
                                <td align="right" class="dottedBottom"> </td>
                            </tr>
                            <tr>
                                <td colspan="5"><strong>Duration of Insulin:</strong> 5:00 hours
                                    <span style="color:#cccccc">|</span>
                                    <strong>Carbohydrates:</strong>
                                    <div class="status_on">On</div>
                                    <span style="color:#cccccc">|</span>
                                </td>
                            </tr>
                        </table>
                        <table width="100%" border="0" cellpadding="0" cellspacing="0" class="settingstable">
                            <tr>
                                <td colspan="2" class="settings_bg_green borderbottom">
                                    <div class="setting_title"><img align="absmiddle" style="margin-top:-4px;"
                                            src="/images/icon_settings.png" /> Settings
                                    </div>
                                </td>
                            </tr>
                            <tr>
                                <td width="50%" class="settings_bg_sub borderbottom"><strong>Alerts</strong></td>
                                <td width="50%" align="left" class="settings_bg_sub borderbottom borderleft">
                                    <strong>Pump Settings</strong>
                                </td>
                            </tr>
                            <tr>
                                <td valign="top" class="padding-0">
                                    <table width="100%" border="0" cellpadding="0" cellspacing="0"
                                        class="settingstable border-0">
                                        <tr>
                                            <td class="dottedBottom"><strong>Alert: Auto-Off</strong></td>
                                            <td class="dottedBottom">
                                                <div class="status_on right-margin-6">On</div>18 hrs
                                            </td>
                                        </tr>
                                        <tr>
                                            <td class="dottedBottom"><strong>Alert: Low Insulin</strong></td>
                                            <td class="dottedBottom">35 u</td>
                                        </tr>
                                        <tr>
                                            <td colspan="2" class="settings_bg_sub borderbottom">
                                                <strong>Reminders</strong>
                                            </td>
                                        </tr>
                                        <tr>
                                            <td class="dottedBottom"><strong>Low BG</strong></td>
                                            <td class="dottedBottom">
                                                <div class="status_off">Off</div>
                                            </td>
                                        </tr>
                                        <tr>
                                            <td class="dottedBottom"><strong>High BG</strong></td>
                                            <td class="dottedBottom">
                                                <div class="status_off">Off</div>
                                            </td>
                                        </tr>
                                        <tr>
                                            <td class="dottedBottom"><strong>Site Change Reminder</strong></td>
                                            <td class="dottedBottom">
                                                <div class="status_on right-margin-6">On</div>
                                                <div class="settings-detail">3<xml:text> </xml:text>days<xml:text>
                                                    </xml:text>9:00 PM</div>
                                            </td>
                                        </tr>
                                        <tr>
                                            <td class="dottedBottom"><strong>Missed Meal Bolus: Reminder 1</strong></td>
                                            <td class="dottedBottom">
                                                <div> – </div>
                                            </td>
                                        </tr>
                                        <tr>
                                            <td class="dottedBottom"><strong>Missed Meal Bolus: Reminder 2</strong></td>
                                            <td class="dottedBottom">
                                                <div> – </div>
                                            </td>
                                        </tr>
                                        <tr>
                                            <td class="dottedBottom"><strong>Missed Meal Bolus: Reminder 3</strong></td>
                                            <td class="dottedBottom">
                                                <div> – </div>
                                            </td>
                                        </tr>
                                        <tr>
                                            <td class="dottedBottom"><strong>Missed Meal Bolus: Reminder 4</strong></td>
                                            <td class="dottedBottom">
                                                <div> – </div>
                                            </td>
                                        </tr>
                                        <tr>
                                            <td class="dottedBottom"><strong>After Bolus BG</strong></td>
                                            <td class="dottedBottom">
                                                <div class="status_off">Off</div>
                                            </td>
                                        </tr>
                                        <tr>
                                            <td class="dottedBottom"><strong>Status</strong></td>
                                            <td class="dottedBottom">
                                                <div class="status_off">Off</div>
                                            </td>
                                        </tr>
                                        <tr>
                                            <td colspan="2" class="settings_bg_sub borderbottom"><strong>CGM
                                                    Alerts</strong></td>
                                        </tr>
                                        <tr>
                                            <td class="dottedBottom"><strong>High Alert</strong></td>
                                            <td class="dottedBottom">
                                                <div class="status_on right-margin-6">On</div>200 mg/dL 1 hr
                                            </td>
                                        </tr>
                                        <tr>
                                            <td class="dottedBottom"><strong>Low Alert</strong></td>
                                            <td class="dottedBottom">
                                                <div class="status_on right-margin-6">On</div>80 mg/dL 30 mins
                                            </td>
                                        </tr>
                                        <tr>
                                            <td class="dottedBottom"><strong>Rise Alert</strong></td>
                                            <td class="dottedBottom">
                                                <div class="status_on right-margin-6">On</div>3 mg/dL/min
                                            </td>
                                        </tr>
                                        <tr>
                                            <td class="dottedBottom"><strong>Fall Alert</strong></td>
                                            <td class="dottedBottom">
                                                <div class="status_on right-margin-6">On</div>3 mg/dL/min
                                            </td>
                                        </tr>
                                        <tr>
                                            <td><strong>Sensor Out of Range</strong></td>
                                            <td>
                                                <div class="status_on right-margin-6">On</div>20 minutes
                                            </td>
                                        </tr>
                                    </table>
                                </td>
                                <td valign="top" class="borderleft padding-0">
                                    <table width="100%" border="0" cellpadding="0" cellspacing="0"
                                        class="settingstable border-0">
                                        <tr>
                                            <td class="dottedBottom"><strong>Quick Bolus</strong></td>
                                            <td class="dottedBottom">
                                                <div class="status_off">Off</div>
                                            </td>
                                        </tr>
                                        <tr>
                                            <td class="dottedBottom"><strong>Max Bolus</strong></td>
                                            <td class="dottedBottom">25 u</td>
                                        </tr>
                                        <tr>
                                            <td class="dottedBottom"><strong>Basal Limit</strong></td>
                                            <td class="dottedBottom">5 u/hr</td>
                                        </tr>
                                        <tr>
                                            <td class="dottedBottom"><strong>Screen Timeout</strong></td>
                                            <td class="dottedBottom">30 sec</td>
                                        </tr>
                                        <tr>
                                            <td class="dottedBottom"><strong>Feature Lock</strong></td>
                                            <td class="dottedBottom">
                                                <div class="status_off">Off</div>
                                            </td>
                                        </tr>
                                        <tr>
                                            <td class="dottedBottom"><strong>Pump Volume: Button</strong></td>
                                            <td class="dottedBottom">Vibrate</td>
                                        </tr>
                                        <tr>
                                            <td class="dottedBottom"><strong>Pump Volume: Quick Bolus</strong></td>
                                            <td class="dottedBottom">Low</td>
                                        </tr>
                                        <tr>
                                            <td class="dottedBottom"><strong>Pump Volume: Bolus</strong></td>
                                            <td class="dottedBottom">Low</td>
                                        </tr>
                                        <tr>
                                            <td class="dottedBottom"><strong>Pump Volume: Reminders</strong></td>
                                            <td class="dottedBottom">Vibrate</td>
                                        </tr>
                                        <tr>
                                            <td class="dottedBottom"><strong>Pump Volume: Alerts</strong></td>
                                            <td class="dottedBottom">Vibrate</td>
                                        </tr>
                                        <tr>
                                            <td class="dottedBottom"><strong>Pump Volume: Alarms</strong></td>
                                            <td class="dottedBottom">Low</td>
                                        </tr>
                                        <td class="dottedBottom"><br /><br /><br /></td>
                                        <td class="dottedBottom" />
                                        <tr>
                                            <td colspan="2" class="settings_bg_sub borderbottom"><strong>CGM
                                                    Settings</strong></td>
                                        </tr>
                                        <tr>
                                            <td class="dottedBottom"><strong>Transmitter ID</strong></td>
                                            <td class="dottedBottom">ABCDEF</td>
                                        </tr>
                                        <tr>
                                            <td class="dottedBottom"><strong>CGM Volume</strong></td>
                                            <td class="dottedBottom">Vibrate</td>
                                        </tr>
                                        <tr>
                                            <td class="dottedBottom"><br /><br /><br /><br /><br /></td>
                                            <td class="dottedBottom" />
                                        </tr>
                                        <tr>
                                            <td colspan="2" class="settings_bg_sub borderbottom"><strong>Control-IQ
                                                    Settings</strong></td>
                                        </tr>
                                        <tr>
                                        <tr>
                                            <td class="dottedBottom"><strong>Control IQ</strong></td>
                                            <td class="dottedBottom">
                                                <div class="status_on">On</div>
                                            </td>
                                        </tr>
                            </tr>
                            <tr>
                            <tr>
                                <td class="dottedBottom"><strong>Weight</strong></td>
                                <td class="dottedBottom">150 lbs </td>
                            </tr>
                            </tr>
                            <tr>
                            <tr>
                                <td class="dottedBottom"><strong>Total Daily Insulin</strong></td>
                                <td class="dottedBottom">75 u
                                </td>
                            </tr>
                            </tr>
                            <tr>
                            <tr>
                                <td class="dottedBottom"><strong>Sleep Schedule 1</strong></td>
                                <td class="dottedBottom">
                                    <div class="status_on right-margin-6">On</div>Everyday
                                    -
                                    1:30 AM -
                                    10:00 AM
                                </td>
                            </tr>
                            </tr>
                            <tr>
                            <tr>
                                <td class="dottedBottom"><strong>Sleep Schedule 2</strong></td>
                                <td class="dottedBottom">
                                    <div class="status_off">Off</div>--
                                    -
                                    11:00 PM -
                                    7:00 AM
                                </td>
                            </tr>
                            </tr>
                        </table>
                        </td>
                        </tr>
                        </table>
                    </div>
                </div>
            </div>
            <div class="floatRight" style="color: #ddd;">
                <div class="RadAjaxPanel" id="ctl00_ContentBody_ctl00_ContentBody_Label1Panel">
                    <span id="Label1">381087060</span>
                </div>
            </div>
        </div>
    </form>
</body>

</html>
    """
        
    def test_device_settings_from_guid(self):

        ciq = ControlIQApi()
        ciq.needs_relogin = lambda: False
        ciq.loginSession = requests.Session()
        ciq.LOGIN_URL = RealControlIQApi.LOGIN_URL
        ciq.login = lambda email, password: True
        webui = WebUIScraper(ciq)

        with requests_mock.Mocker() as m:
            m.get('https://tconnect.tandemdiabetes.com/myaccount/DeviceSettings.aspx?guid=00000000-0000-0000-0000-000000000001',
                request_headers=base_headers(),
                text=self.PUMP_SETTINGS_HTML)

            profiles, settings = webui.device_settings_from_guid('00000000-0000-0000-0000-000000000001')
            self.assertListEqual(profiles, [Profile(**{
                'title': 'A', 
                'active': True, 
                'segments': [ProfileSegment(**{
                    'display_time': 'Midnight', 
                    'time': '12:00 AM', 
                    'basal_rate': 0.800,
                    'correction_factor': 30.0,
                    'carb_ratio': 6.0,
                    'target_bg_mgdl': 110
                }), ProfileSegment(**{
                    'display_time': '6:00 AM', 
                    'time': '6:00 AM', 
                    'basal_rate': 1.250,
                    'correction_factor': 30,
                    'carb_ratio': 6.0,
                    'target_bg_mgdl': 110
                }), ProfileSegment(**{
                    'display_time': '11:00 AM', 
                    'time': '11:00 AM', 
                    'basal_rate': 1.000,
                    'correction_factor': 30,
                    'carb_ratio': 6.0,
                    'target_bg_mgdl': 110
                }), ProfileSegment(**{
                    'display_time': 'Noon', 
                    'time': '12:00 PM', 
                    'basal_rate': 0.800,
                    'correction_factor': 30,
                    'carb_ratio': 6.0,
                    'target_bg_mgdl': 110
                })], 
                'calculated_total_daily_basal': 21.65, 
                'insulin_duration_min': 5*60,
                'carbs_enabled': True
            })])

            self.assertDictEqual(settings.raw_settings, {
                'Alerts': {
                    'Alert: Auto-Off': {'text': '18 hrs', 'value': True},
                    'Alert: Low Insulin': {'text': '35 u'}
                },
                'CGM Alerts': {
                    'Fall Alert': {'text': '3 mg/dL/min', 'value': True},
                    'High Alert': {'text': '200 mg/dL 1 hr', 'value': True},
                    'Low Alert': {'text': '80 mg/dL 30 mins', 'value': True},
                    'Rise Alert': {'text': '3 mg/dL/min', 'value': True},
                    'Sensor Out of Range': {'text': '20 minutes', 'value': True}
                },
                'CGM Settings': {
                    'CGM Volume': {'text': 'Vibrate'},
                    'Transmitter ID': {'text': 'ABCDEF'}
                },
                'Control-IQ Settings': {
                    'Control IQ': {'text': '', 'value': True},
                    'Sleep Schedule 1': {'text': 'Everyday - 1:30 AM - 10:00 AM', 'value': True},
                    'Sleep Schedule 2': {'text': '-- - 11:00 PM - 7:00 AM', 'value': False},
                    'Total Daily Insulin': {'text': '75 u'},
                    'Weight': {'text': '150 lbs'}
                },
                'Pump Settings': {
                    'Basal Limit': {'text': '5 u/hr'},
                    'Feature Lock': {'text': '', 'value': False},
                    'Max Bolus': {'text': '25 u'},
                    'Pump Volume: Alarms': {'text': 'Low'},
                    'Pump Volume: Alerts': {'text': 'Vibrate'},
                    'Pump Volume: Bolus': {'text': 'Low'},
                    'Pump Volume: Button': {'text': 'Vibrate'},
                    'Pump Volume: Quick Bolus': {'text': 'Low'},
                    'Pump Volume: Reminders': {'text': 'Vibrate'},
                    'Quick Bolus': {'text': '', 'value': False},
                    'Screen Timeout': {'text': '30 sec'}
                },
                'Reminders': {
                    'After Bolus BG': {'text': '', 'value': False},
                    'High BG': {'text': '', 'value': False},
                    'Low BG': {'text': '', 'value': False},
                    'Missed Meal Bolus: Reminder 1': {'text': '–'},
                    'Missed Meal Bolus: Reminder 2': {'text': '–'},
                    'Missed Meal Bolus: Reminder 3': {'text': '–'},
                    'Missed Meal Bolus: Reminder 4': {'text': '–'},
                    'Site Change Reminder': {'text': '3 days 9:00 PM', 'value': True},
                    'Status': {'text': '', 'value': False}
                },
                'upload_date': 'Jan 09, 2022'
            })
            self.assertEqual(settings.low_bg_threshold, 80)
            self.assertEqual(settings.high_bg_threshold, 200)



if __name__ == '__main__':
    unittest.main()