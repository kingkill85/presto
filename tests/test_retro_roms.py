import ast
import os
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('retro_roms', ROOT/'device/lib/retro_roms.py')
roms = importlib.util.module_from_spec(spec)
spec.loader.exec_module(roms)


class RomDiscoveryTests(unittest.TestCase):
    def test_nested_formats_case_and_missing_roots(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            (root/'nes').mkdir()
            (root/'nes'/'Mario.NES').write_bytes(b'NES\x1a')
            (root/'a.GBC').write_bytes(b'')
            (root/'b.gg').write_bytes(b'')
            (root/'c.sms').write_bytes(b'')
            (root/'a.sav').write_bytes(b'')
            (root/'notes.txt').write_bytes(b'')
            found=roms.discover((folder, folder+'/absent'))
            self.assertEqual([Path(p).name for p in found], ['a.GBC','b.gg','c.sms','Mario.NES'])

    def test_cgb_header_overrides_gb_extension(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'dual.gb'
            data=bytearray(0x150)
            p.write_bytes(data)
            self.assertEqual(roms.system_for(str(p))[1],'gbaudiocore')
            data[0x143]=0x80
            p.write_bytes(data)
            self.assertEqual(roms.system_for(str(p))[1],'gbccore')

    def test_lazy_loading_only_selected_core(self):
        for ext, name in (('.gbc','gbccore'),('.gg','smscore'),('.sms','smscore'),('.nes','nescore')):
            core=object()
            with patch('builtins.__import__',return_value=core) as load:
                got, period=roms.load_core('game'+ext)
                self.assertIs(got,core)
                self.assertGreater(period,16000)
                load.assert_called_once_with(name)

    def test_unknown_format_is_rejected(self):
        with self.assertRaises(ValueError):
            roms.system_for('game.gba')


class RomReadTests(unittest.TestCase):
    def test_large_rom_is_read_into_one_allocation(self):
        tree=ast.parse((ROOT/'device/lib/retro.py').read_text())
        tree.body=[node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='read_rom']
        env={'os':os}
        exec(compile(tree,'retro.py','exec'),env)
        data=bytes(range(256))*4096
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'large.gbc'
            path.write_bytes(data)
            self.assertEqual(env['read_rom'](str(path)),data)

    def test_incomplete_read_is_rejected(self):
        tree=ast.parse((ROOT/'device/lib/retro.py').read_text())
        tree.body=[node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='read_rom']
        env={'os':os}
        exec(compile(tree,'retro.py','exec'),env)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'short.gb'
            path.write_bytes(b'123')
            with patch.object(os,'stat',return_value=(0,0,0,0,0,0,10)):
                with self.assertRaises(ValueError):
                    env['read_rom'](str(path))


if __name__=='__main__':
    unittest.main()
