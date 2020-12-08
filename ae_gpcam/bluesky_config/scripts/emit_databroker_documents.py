from itertools import count

from bluesky.callbacks.zmq import Publisher
from databroker import Broker


db = Broker.named("xpd")

zmq_publisher = Publisher("xf28id2-ca1:5577", prefix=b"raw")
run_uid = "88e450ff-b1a7-4a17-a353-ab40653b7675"

extra = count()
for name, doc in db[run_uid].documents():
    print(f"trying to emit {name}")
    doc = dict(doc)
    if name == 'descriptor':
        doc['data_keys']['extra'] =  {
                        "dtype": "number",
                        "source": "computed",
                        "units": "arb",
                        "shape": [],
                    }
        zmq_publisher('descriptor', doc)
    if name =='event_page':
        for ev in unpack_event_page(doc):
            for j in range(5):
                new_seq = next(extra)
                ev['seq_num'] = new_seq
                ev['uid'] = str(uuid.uuid4())
                ev['data']['extra'] = 5
                ev['timestamps']['extra'] = 0
                zmq_publisher('event', ev)
    elif name == 'datum_page':
        for datum in unpack_datum_page(doc):
            zmq_publisher('datum', datum)
    else:
        zmq_publisher(name, doc)
