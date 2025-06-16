gopy_build:
	rm -f src/trufnetwork_sdk_c_bindings/*.so
	gopy gen -output=src/trufnetwork_sdk_c_bindings -vm=python3 -name=trufnetwork_sdk_c_bindings ./bindings
	cd src/trufnetwork_sdk_c_bindings && python3 build.py