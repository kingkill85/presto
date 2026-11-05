"""Original CGB audio fixture at both CPU speeds; no third-party game data."""
import gbccore as core
from rom_fixtures import gb_audio_rom
fb=bytearray(240*240*2)
block=bytearray(core.audio_samples*4)
reference=None
for speed in (False,True):
    rom=gb_audio_rom(0xff,color=True,double_speed=speed)
    core.init(rom)
    for n in range(8):
        assert not core.frame(fb,0,0,0,False)
        core.audio(block,4095,60)
    assert any(block[i:i+4] != block[:4] for i in range(4,len(block),4))
    if reference is None:
        reference=bytes(block)
    else:
        assert reference==bytes(block), 'CPU speed changed audio pitch/timing'
    state=bytearray(core.state_size())
    core.save_state(state)
    core.frame(fb,0,0,0,False)
    core.audio(block,4095,60)
    expected=bytes(block)
    core.load_state(state)
    core.frame(fb,0,0,0,False)
    core.audio(block,4095,60)
    assert bytes(block)==expected
    try:
        core.load_state(state[:-4])
        raise AssertionError('Truncated state accepted')
    except ValueError:
        pass
    print('CGB audio speed/state OK:',2 if speed else 1)
assert core.state_id=='presto-gbc-audio-v2'
