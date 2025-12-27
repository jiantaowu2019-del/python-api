import threading
import time
import requests

BASE = "http://127.0.0.1:8000/api/jobs"

def creator(n=50):
    for i in range(n):
        requests.post(BASE, json={"payload": f"job-{i}"})

def lister(seconds=3):
    end = time.time() + seconds
    while time.time() < end:
        requests.get(BASE)          # list
        requests.get(BASE + "/stats")

def deleter(seconds=3):
    end = time.time() + seconds
    while time.time() < end:
        r = requests.get(BASE)
        jobs = r.json()
        if jobs:
            # 随便删一个（不管状态）
            jid = jobs[0]["id"]
            requests.delete(f"{BASE}/{jid}")

threads = [
    threading.Thread(target=creator),
    threading.Thread(target=lister),
    threading.Thread(target=deleter),
]

for t in threads: t.start()
for t in threads: t.join()

print("done")
