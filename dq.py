from collections import deque
import random 
import statistics
from datetime import datetime, timedelta

q = deque(maxlen=5)
now = datetime.now()

for i in range(2):
    s = random.randint(0, 5)
    dt = now + timedelta(minutes=i*60, seconds=s)
    q.appendleft(dt)

l = len(q)
if l > 1:
    print(q)

    deltas = []

    for i in range(l):
        if i < l-1:
            dt1 = q[i]
            dt2 = q[i+1]
            deltas.append(int((dt1-dt2).seconds))

    print("deltas:", deltas)
    d = int(statistics.median(deltas))
    print(d)

    if d > 3600: 
        pass  # use 3600

    if d < 900:
        pass # use 900

# print(int((dt2-dt1).seconds))