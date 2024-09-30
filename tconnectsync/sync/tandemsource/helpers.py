
def insulin_float_round(amt):
    if type(amt) != float:
        return amt
    return round(amt, 2)

def insulin_milliunits_to_real(amtMilli):
    return insulin_float_round(amtMilli / 1000)