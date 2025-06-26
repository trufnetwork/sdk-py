gopy_build:
	rm -f src/trufnetwork_sdk_c_bindings/*.so
	gopy gen -output=src/trufnetwork_sdk_c_bindings -vm=python3 -name=trufnetwork_sdk_c_bindings ./bindings
	cd src/trufnetwork_sdk_c_bindings && \
	make build
	if [ `uname` = "Linux" ]; then \
		patchelf --set-rpath '$$ORIGIN' src/trufnetwork_sdk_c_bindings/_trufnetwork_sdk_c_bindings.so; \
	elif [ `uname` = "Darwin" ]; then \
		install_name_tool -add_rpath @loader_path src/trufnetwork_sdk_c_bindings/_trufnetwork_sdk_c_bindings.so; \
	fi