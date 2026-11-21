"""Level-choice diagnostic on current code with the pre-switch risk model (Eq. (5) occupancy).
Usage: python lcd_occ.py <code_root> <out.json>"""
import sys, os, runpy, dataclasses
sys.path.insert(0, os.path.join(sys.argv[1], 'src'))
import prism_repro.config as C
f = {x.name: x for x in dataclasses.fields(C.PrismConfig)}
f['risk_model'].default = 'occupancy'
C.PrismConfig.__init__.__defaults__  # noqa
# rebuild the dataclass with the new default
C.PrismConfig = dataclasses.make_dataclass('PrismConfig', [(x.name, x.type, dataclasses.field(default=x.default) if x.default is not dataclasses.MISSING else dataclasses.field(default_factory=x.default_factory)) for x in dataclasses.fields(C.PrismConfig)], bases=(C.PrismConfig,), frozen=True)
import prism_repro.experiment as E; E.PrismConfig = C.PrismConfig
assert C.PrismConfig().risk_model == 'occupancy'
sys.argv = ['level_choice_diagnostic.py', sys.argv[1], sys.argv[2]]
runpy.run_path(os.path.join(sys.argv[1], 'scripts', 'revision', 'level_choice_diagnostic.py'), run_name='__main__')
