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
# IMPORTANT: pass LDFLAGS as a make command-line argument, not as an env
# var prefix. The gopy-emitted Makefile defines `LDFLAGS = ...` itself,
# and Make precedence gives Makefile assignments priority over env vars
# (command-line args win over both). `LDFLAGS=... make build` would be
# silently ignored.
SUBMAKE_BUILD := make build LDFLAGS="-undefined dynamic_lookup -Wl,-flat_namespace"
else
SUBMAKE_BUILD := make build
endif

# gopy's own template emits a Windows-only line to fix pybindgen's PyInit_
# declaration (see the "windows-only sed hack" comment it generates), but
# indents that one recipe line with two spaces instead of a tab, which GNU
# Make rejects as "missing separator" before it ever reaches a shell. This
# is gopy's bug, not ours: the line either doesn't exist (Linux/macOS
# targets never emit it) or is well-formed once fixed upstream, so the
# check below is content-matched and OS-gated to stay a no-op everywhere
# except an affected Windows build.
ifeq ($(OS),Windows_NT)
WINGOPY_PYINIT_FIX := sed -i 's|^  sed -i "s/ PyInit_/|\tsed -i "s/ PyInit_/|' src/trufnetwork_sdk_c_bindings/Makefile
else
WINGOPY_PYINIT_FIX := true
endif

gopy_build:
	rm -f src/trufnetwork_sdk_c_bindings/*.so src/trufnetwork_sdk_c_bindings/*.pyd src/trufnetwork_sdk_c_bindings/*.dll
	gopy gen -output=src/trufnetwork_sdk_c_bindings -vm=python3 -name=trufnetwork_sdk_c_bindings $(DYNAMIC_LINK_FLAG) ./bindings
	@$(WINGOPY_PYINIT_FIX)
	cd src/trufnetwork_sdk_c_bindings && \
	$(SUBMAKE_BUILD)
	if [ `uname` = "Linux" ]; then \
		patchelf --set-rpath '$$ORIGIN' src/trufnetwork_sdk_c_bindings/_trufnetwork_sdk_c_bindings.so; \
	elif [ `uname` = "Darwin" ]; then \
		set -e; \
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
		for f in src/trufnetwork_sdk_c_bindings/_trufnetwork_sdk_c_bindings.so \
		         src/trufnetwork_sdk_c_bindings/trufnetwork_sdk_c_bindings_go.so; do \
			if otool -L "$$f" | grep -E 'Python\.framework|libpython' >/dev/null; then \
				echo "FATAL: $$f still references Python (Python.framework or libpython). This will SIGSEGV under non-build-time Python interpreters (Homebrew/conda/uv). Verify -dynamic-link=true and the LDFLAGS sub-make override are taking effect."; \
				exit 1; \
			fi; \
		done; \
	fi