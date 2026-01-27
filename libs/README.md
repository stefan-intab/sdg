Protobuf

1. Setup protoc:

2. Install python modules:
pip install protobuf mypy-protobuf

3. Create a proto file with schema:
In this example: 
intabcloud_telemetry_v1.proto

4. Compile proto file and generate stubs for python:
protoc -I. \
  --python_out=. \
  --mypy_out=. \
  intabcloud_telemetry_v1.proto

