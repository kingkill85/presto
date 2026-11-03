# MicroPython v1.26.0; NixOS: MKDIR=mkdir RM=rm
MPY_DIR ?= ../../../micropython
MOD = nescore
SRC = nescore.c ../common/mini_libc.c
ARCH = armv7emsp
CFLAGS_EXTRA = -O3 -fno-semantic-interposition -fno-strict-aliasing -Wno-error -std=gnu11 -Wno-unused-function -Wno-unused-variable -DNDEBUG
include ../common/flags.mk
include $(MPY_DIR)/py/dynruntime.mk

$(BUILD)/nescore.o: $(wildcard vendor/*.c vendor/*.h vendor/mapper/*.c) ../common/retro_fb.h ../common/mpy_alloc.h
