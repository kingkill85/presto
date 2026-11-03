# Decoder, C++ runtime and SD stream probes, not a playable ScummVM core.
MPY_DIR ?= ../../../micropython
SCUMM_DIR ?= build/frank-quest
MOD = scummprobe
SRC = probe.c file_bridge.c ../common/mini_libc.c
SRC_O += build/runtime_ready.o
ARCH = armv7emsp
CFLAGS += -I$(SCUMM_DIR)/src
include ../common/flags.mk
include $(MPY_DIR)/py/dynruntime.mk

SCUMM_FLAGS = $(CFLAGS_ARCH) -Os -std=c++17 -fno-exceptions -fno-rtti \
    -fno-builtin-malloc -fno-builtin-calloc -fno-builtin-realloc -fno-builtin-free \
    -fno-threadsafe-statics -fno-tree-loop-distribute-patterns \
    -ffunction-sections -fdata-sections -DNDEBUG -D__RP2350__=1 \
    -DENABLE_SCUMM=1 -DCABAL_HAVE_STDINT_H=1 -I$(SCUMM_DIR)/src -I$(SCUMM_DIR)/src/engines

build/probe_cpp.o: probe.cpp Makefile
	$(MKDIR) -p build
	$(CROSS)g++ $(SCUMM_FLAGS) -c $< -o $@

build/bomp.o: $(SCUMM_DIR)/src/engines/scumm/bomp.cpp Makefile
	$(MKDIR) -p build
	$(CROSS)g++ $(SCUMM_FLAGS) -c $< -o $@

build/decoder.o: build/probe_cpp.o build/bomp.o
	$(CROSS)ld -r --gc-sections -u scumm_bomp_probe -o $@ $^

build/runtime_cpp.o: runtime.cpp runtime.h Makefile
	$(MKDIR) -p build
	$(CROSS)g++ $(SCUMM_FLAGS) -c $< -o $@

build/stream.o: $(SCUMM_DIR)/src/common/stream.cpp Makefile
	$(MKDIR) -p build
	$(CROSS)g++ $(SCUMM_FLAGS) -c $< -o $@

build/str.o: $(SCUMM_DIR)/src/common/str.cpp Makefile
	$(MKDIR) -p build
	$(CROSS)g++ $(SCUMM_FLAGS) -c $< -o $@

build/memorypool.o: $(SCUMM_DIR)/src/common/memorypool.cpp Makefile
	$(MKDIR) -p build
	$(CROSS)g++ $(SCUMM_FLAGS) -c $< -o $@

build/fs.cpp: $(SCUMM_DIR)/src/backends/fs/rp2350/rp2350-fs.cpp prepare_fs.py
	$(MKDIR) -p build
	$(PYTHON) prepare_fs.py $< $@

build/fs.o: build/fs.cpp Makefile
	$(CROSS)g++ $(SCUMM_FLAGS) -c $< -o $@

build/heap.o: heap.c runtime.h Makefile
	$(MKDIR) -p build
	$(CROSS)gcc $(CFLAGS_ARCH) -Os -ffunction-sections -fdata-sections -c $< -o $@

build/dlmalloc.c: $(SCUMM_DIR)/drivers/dlmalloc.c prepare_allocator.py
	$(MKDIR) -p build
	$(PYTHON) prepare_allocator.py $< $@

build/dlmalloc.o: build/dlmalloc.c Makefile
	$(MKDIR) -p build
	$(CROSS)gcc $(CFLAGS_ARCH) -Os -ffunction-sections -fdata-sections \
	    -fno-tree-loop-distribute-patterns -DONLY_MSPACES=1 -DHAVE_MMAP=0 \
	    -DHAVE_MORECORE=0 -DNO_MALLOC_STATS=1 -DUSE_LOCKS=0 \
	    -DABORT_ON_ASSERT_FAILURE=1 -DMALLOC_FAILURE_ACTION= \
	    -DLACKS_SYS_MMAN_H=1 -DLACKS_UNISTD_H=1 -DLACKS_SYS_PARAM_H=1 \
	    -DLACKS_TIME_H=1 -Dmalloc_getpagesize=4096 -DFOOTERS=1 \
	    -DPROCEED_ON_ERROR=0 -c $< -o $@

RUNTIME_OBJECTS = build/decoder.o build/runtime_cpp.o build/stream.o build/str.o \
    build/memorypool.o build/heap.o build/dlmalloc.o build/fs.o

build/runtime_link.o: $(RUNTIME_OBJECTS)
	$(CROSS)ld -r --gc-sections -u scumm_bomp_probe -u scumm_runtime_probe \
	    -u scumm_heap_begin -u scumm_heap_end -u scumm_file_probe -u scumm_runtime_reset -o $@ $^

build/runtime_ready.o: build/runtime_link.o prepare_data.py
	$(PYTHON) prepare_data.py $< $@ --inputs $(RUNTIME_OBJECTS)
