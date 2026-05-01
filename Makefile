gopy_build:
	rm -f src/trufnetwork_sdk_c_bindings/*.so
	gopy gen -output=src/trufnetwork_sdk_c_bindings -vm=python3 -name=trufnetwork_sdk_c_bindings ./bindings
	cd src/trufnetwork_sdk_c_bindings && \
	make build
	if [ `uname` = "Linux" ]; then \
		patchelf --set-rpath '$$ORIGIN' src/trufnetwork_sdk_c_bindings/_trufnetwork_sdk_c_bindings.so; \
	elif [ `uname` = "Darwin" ]; then \
		install_name_tool -id @loader_path/trufnetwork_sdk_c_bindings_go.so \
			src/trufnetwork_sdk_c_bindings/trufnetwork_sdk_c_bindings_go.so; \
		GO_SO_OLD=`otool -L src/trufnetwork_sdk_c_bindings/_trufnetwork_sdk_c_bindings.so | awk '/trufnetwork_sdk_c_bindings_go\.so/ {print $$1; exit}'`; \
		if [ -z "$$GO_SO_OLD" ]; then \
			echo "FATAL: _trufnetwork_sdk_c_bindings.so does not reference trufnetwork_sdk_c_bindings_go.so"; exit 1; \
		fi; \
		install_name_tool -change "$$GO_SO_OLD" @loader_path/trufnetwork_sdk_c_bindings_go.so \
			src/trufnetwork_sdk_c_bindings/_trufnetwork_sdk_c_bindings.so; \
		install_name_tool -add_rpath @loader_path \
			src/trufnetwork_sdk_c_bindings/_trufnetwork_sdk_c_bindings.so; \
		echo "=== otool -L (post-fix) ==="; \
		otool -L src/trufnetwork_sdk_c_bindings/_trufnetwork_sdk_c_bindings.so; \
		otool -L src/trufnetwork_sdk_c_bindings/trufnetwork_sdk_c_bindings_go.so; \
	fi