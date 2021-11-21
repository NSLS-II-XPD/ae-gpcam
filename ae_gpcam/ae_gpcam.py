import requests


def ae_gpcam():
   response = requests.get("http://127.0.0.1:8080")
   print(response)


if __name__ == "__main__":
    ae_gpcam()
