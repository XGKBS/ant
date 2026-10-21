"""Same-model rendering ablation: frozen 4D renderer vs 4E icons/diagnostics."""
import argparse,importlib.util,json,os
from pathlib import Path
from time import perf_counter
from benchmarks.phase3 import populated
from benchmarks.phase4c import distribution
from benchmarks.phase4e import fingerprint

def main():
    p=argparse.ArgumentParser();p.add_argument('--baseline',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    os.environ['SDL_VIDEODRIVER']='dummy';os.environ['SDL_AUDIODRIVER']='dummy'
    import pygame
    from ui.renderer import Renderer
    spec=importlib.util.spec_from_file_location('original_phase4d_renderer',a.baseline);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    pygame.init();screen=pygame.display.set_mode((1200,800))
    with a.output.open('w') as out:
        for count in (100,500,1000):
            e=populated(count,'distributed',512)
            for _ in range(5):e.advance(1)
            check=fingerprint(e);results={}
            for mode in ('phase4d','phase4e_closed','phase4e_open'):
                r=module.Renderer(screen,e) if mode=='phase4d' else Renderer(screen,e)
                if mode=='phase4e_open':r.economy_open=True
                r.focus(e,0);r.draw(e);times=[]
                for _ in range(120):
                    t=perf_counter();r.draw(e);pygame.display.flip();times.append(perf_counter()-t)
                results[mode]=distribution(times)
                assert fingerprint(e)==check
            record=dict(initial_ants=count,actual_ants=len(e.world.ants),turn=e.turn,overlays='off',view='colony focus',driver='dummy',frames=120,**results)
            out.write(json.dumps(record)+'\n');out.flush();print(json.dumps(record),flush=True)
    pygame.quit()
if __name__=='__main__':main()
