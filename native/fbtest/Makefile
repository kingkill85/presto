# Build: make MPY_DIR=/path/to/micropython (v1.26.0, like the firmware)
MPY_DIR ?= ../../../micropython
MOD = fbtest
SRC = fbtest.c ../common/mini_libc.c
ARCH = armv7emsp
include ../common/flags.mk
include $(MPY_DIR)/py/dynruntime.mk
