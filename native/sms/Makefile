# MicroPython v1.26.0; NixOS: MKDIR=mkdir RM=rm
MPY_DIR ?= ../../../micropython
MOD = smscore
SRC = smscore.c ../common/mini_libc.c vendor/scheduler.c
ARCH = armv7emsp
CFLAGS_EXTRA = -O3 -fno-semantic-interposition -fno-strict-aliasing -std=gnu11 -Wno-unused-function -Wno-unused-variable -DNDEBUG -Ivendor -include ../common/mpy_alloc.h
include ../common/flags.mk
include $(MPY_DIR)/py/dynruntime.mk

$(BUILD)/smscore.o: presto_psg.h $(wildcard vendor/*.c vendor/*.h) ../common/retro_fb.h ../common/mpy_alloc.h
