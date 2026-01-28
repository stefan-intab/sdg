## Protobuf

### Setup
1. Setup protoc:<br>
`sudo apt install protobuf-compiler`

2. Install python modules:<br>
`pip install protobuf mypy-protobuf`

3. Create a proto file with schema:<br>
In this example: 
intabcloud_telemetry_v1.proto

4. Compile proto file and generate stubs for python:<br>
```
protoc -I. \
  --python_out=. \
  --mypy_out=. \
  intabcloud_telemetry_v1.proto
```





### Extract oneof key:
```
lv = last_value  # type: LastValue

key = lv.WhichOneof("key")

if key == "channel_id":
    channel_id = lv.channel_id
    ts = lv.ts
    value = lv.value

elif key == "signal_type":
    signal_type = lv.signal_type
    ts = lv.ts
    value = lv.value

else:
    # No key set (possible if message is partially filled)
    raise ValueError("LastValue without key")
```