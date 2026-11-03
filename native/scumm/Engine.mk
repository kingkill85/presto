MPY_DIR ?= ../../../micropython
SCUMM_DIR ?= build/frank-quest
MOD = scummcore
BUILD = build/engine
SRC = engine_bridge.c file_bridge.c heap.c
SRC_O += build/engine/core_ready.o
ARCH = armv7emsp
CFLAGS += -I$(SCUMM_DIR)/src -DSCUMM_ENGINE=1
include ../common/flags.mk
include $(MPY_DIR)/py/dynruntime.mk
