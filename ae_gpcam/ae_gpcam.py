import pprint
import time as ttime

import requests


def ae_gpcam():
    response = requests.get("http://127.0.0.1:60610")
    print(response.request, response.json())

    response = requests.post("http://localhost:60610/environment/open")
    pprint.pprint(response.json())

    ttime.sleep(5)

    response = requests.get("http://127.0.0.1:60610/status")
    pprint.pprint(response.json())

    response = requests.get("http://localhost:60610/plans/allowed")
    #pprint.pprint(response.json())

    response = requests.get("http://localhost:60610/devices/allowed")
    #pprint.pprint(response.json())

    response = requests.post(
       "http://localhost:60610/queue/item/add",
       json={"item": {"name": "count", "args": [["det1", "det2"]], "item_type": "plan"}}
    )
    print(response.headers)
    pprint.pprint(response.json())

    response = requests.post("http://localhost:60610/queue/start")
    pprint.pprint(response.json())

    response = requests.post("http://localhost:60610/environment/close")
    print(response.url, response.json())


if __name__ == "__main__":
    ae_gpcam()
