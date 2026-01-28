from datetime import datetime, timedelta
import httpx, pprint, json
import config


def generate_header(access_token: str) -> dict:
    header = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    # print(f"Header: {header}")
    return header

def authenticate():
    url = "https://api2.smalldatagarden.fi/users"
    payload = {"username": config.USERNAME, "password": config.PASSWORD}

    try:
        r = httpx.post(url=url, json=payload, timeout=5.0)
        r.raise_for_status()
    except Exception as e:
        print(f"Error authenticating: {e}")
        return

    access_token = r.json().get("access_token")
    print(f"Access token: {access_token}")

    return access_token

def fetch_device_groups_and_latest_payload(token: str):
    url = "https://api2.smalldatagarden.fi/devicegroups"
    headers = generate_header(token)
    try:    
        r = httpx.get(url=url, headers=headers)
        r.raise_for_status()
    
    except Exception as e:
        print(f"Error retrieving device groups: {e}")
        return
    
    pp = pprint.PrettyPrinter(indent=4)
    pp.pprint(r.json())

def fetch_device_data_for_period(token, device_id=config.DEVICE1, hours=4):
    url = f"https://api2.smalldatagarden.fi/devices/{device_id}/data"
    now = datetime.now()
    period_from = now - timedelta(hours=hours)
    from_str = datetime.strftime(period_from, '%Y-%m-%d %H:%M')
    to_str = datetime.strftime(now, '%Y-%m-%d %H:%M')
    payload = {
        "from_date": from_str,
        # "from_date": "2020-10-01 00:00",
        "to_date": to_str
    }
    print(f"Payload: {payload}")
    headers = generate_header(token)

    try:
        r = httpx.post(url=url, headers=headers, json=payload)
        r.raise_for_status()
    except Exception as e:
        print(f"Error retrieving device data: {e}")
        return

    # pp = pprint.PrettyPrinter(indent=4)
    # pp.pprint(r.json())

    filename = f"{device_id}_{from_str}-{to_str}.json"
    with open(filename, "w") as f:
        json.dump(r.json(), f, indent=4)


def update_device_intervals(token, d_ids: list, transmit_int=3600, sample_int=900):
    headers = generate_header(token)
    payload =  {
        "TRANSMIT_INTERVAL": transmit_int,
        "MEASUREMENT_INTERVAL": sample_int,
    }
    print(f"Payload: {payload}")
    for id in d_ids:
        url = f"https://api2.smalldatagarden.fi/devices/{id}/downlink"
        try: 
            r = httpx.post(url=url, headers=headers, json=payload)
            r.raise_for_status()
        except Exception as e:
            print(f"Error updating device intervals: {e}")
            return

        pp = pprint.PrettyPrinter(indent=4)
        pp.pprint(r.json())

def get_timezone(token):
    headers = generate_header(token)
    url = "https://api2.smalldatagarden.fi/users/timezone"
    try: 
        r = httpx.get(url, headers=headers)
        r.raise_for_status()
    except Exception as e:
        print(f"Error getting timezone: {e}")
        return

    pp = pprint.PrettyPrinter(indent=4)
    pp.pprint(r.json())


def set_timezone(token, tz="UTC"):
    headers = generate_header(token)
    url = "https://api2.smalldatagarden.fi/users/timezone"
    payload = {"timezone": tz}
    try: 
        r = httpx.put(url, headers=headers, json=payload)
        r.raise_for_status()
    except Exception as e:
        print(f"Error getting timezone: {e}")
        return

    pp = pprint.PrettyPrinter(indent=4)
    pp.pprint(r.json())    


token = authenticate()
# token = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpYXQiOjE3NjE3MzkzNDMsIm5iZiI6MTc2MTczOTM0MywianRpIjoiYTc3ZWJlY2MtNTgyMS00NzNlLTlmMTUtODEwZDRmOTQ5NWRmIiwiZXhwIjoxNzYxNzQwMjQzLCJpZGVudGl0eSI6NTM0LCJmcmVzaCI6ZmFsc2UsInR5cGUiOiJhY2Nlc3MifQ.F-z9UIMgkwJb_cyqZkKTDjLgJ6SwS8EIFBCKVqgsCE8"
if token:
    fetch_device_groups_and_latest_payload(token)
    # set_timezone(token, tz="UTC")
    # get_timezone(token)
    fetch_device_data_for_period(token, config.DEVICE1, hours=36)
    fetch_device_data_for_period(token, config.DEVICE3, hours=36)

    # update_device_intervals(token, [config.DEVICE1, config.DEVICE3], transmit_int=1200, sample_int=300)
    # update_device_intervals(token, [config.DEVICE1, config.DEVICE3], transmit_int=300, sample_int=60)
    # update_device_intervals(token, [config.DEVICE1, config.DEVICE2])

