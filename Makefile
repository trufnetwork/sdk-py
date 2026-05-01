UNAME_S := $(shell uname)

# On macOS, decouple both gopy artifacts from a specific libpython:
#   * `-dynamic-link=true` switches the #cgo LDFLAGS in the generated .go
#     file from `-L... -lpython3.12` to LDSHARED-derived flags
#     (`-undefined dynamic_lookup`), so the Go .so defers Python symbols
#     to whoever loads it.
#   * Overriding LDFLAGS for the gopy-emitted sub-make does the same for
#     the gcc step that links the Python C extension wrapper
#     (`_trufnetwork_sdk_c_bindings.so`); otherwise gopy hard-codes
#     `pycfg.LdFlags` regardless of `-dynamic-link`, leaving the wrapper
#     bound to the build-time libpython and triggering the Homebrew
#     SIGSEGV the PR is meant to prevent.
# `-undefined dynamic_lookup` is on cgo's denylist, so widen the allow
# regex too.
ifeq ($(UNAME_S),Darwin)
DYNAMIC_LINK_FLAG := -dynamic-link=true
export CGO_LDFLAGS_ALLOW := .*
SUBMAKE_BUILD := LDFLAGS="-undefined dynamic_lookup -Wl,-flat_namespace" make build
else
SUBMAKE_BUILD := make build
endif

gopy_build:
	rm -f src/trufnetwork_sdk_c_bindings/*.so
	gopy gen -output=src/trufnetwork_sdk_c_bindings -vm=python3 -name=trufnetwork_sdk_c_bindings $(DYNAMIC_LINK_FLAG) ./bindings
	cd src/trufnetwork_sdk_c_bindings && \
	$(SUBMAKE_BUILD)
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