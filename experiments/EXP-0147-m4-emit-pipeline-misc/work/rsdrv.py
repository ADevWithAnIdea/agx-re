"""Driver for the persistent render sweep runner (watchdog + restart)."""
import json, os, signal, subprocess, threading

class RenderRunner:
    def __init__(self, source, exe='./rendersweep', fast_math=False):
        self.source=source; self.exe=exe; self.fast_math=fast_math
        self.proc=None; self.restarts=0; self._start()
    def _start(self):
        cmd=[self.exe,'--source',self.source]+(['--fast-math'] if self.fast_math else [])
        self.proc=subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE,text=True,bufsize=1,start_new_session=True)
        ln=self._readline(60)
        if not ln or not ln.startswith('READY'):
            err=self.proc.stderr.read() if self.proc.stderr else ''
            raise RuntimeError(f'rendersweep not READY: {ln!r} {err}')
        self.device=ln.split(None,1)[1].strip()
    def _readline(self,timeout):
        res=[None]
        def rd(): res[0]=self.proc.stdout.readline()
        t=threading.Thread(target=rd,daemon=True); t.start(); t.join(timeout)
        return None if t.is_alive() else res[0]
    def _kill(self):
        if self.proc and self.proc.poll() is None:
            try: os.killpg(os.getpgid(self.proc.pid), signal.SIGKILL)
            except ProcessLookupError: pass
        try: self.proc.wait(timeout=5)
        except Exception: pass
    def request(self, req, timeout=10.0):
        try:
            self.proc.stdin.write(json.dumps(req)+'\n'); self.proc.stdin.flush()
        except (BrokenPipeError, ValueError):
            self._kill(); self.restarts+=1; self._start()
            return {'id':req.get('id'),'status':'HANG','error':'broken pipe','restarted':True}
        ln=self._readline(timeout)
        if ln is None:
            self._kill(); self.restarts+=1; self._start()
            return {'id':req.get('id'),'status':'HANG','error':f'no response in {timeout}s','restarted':True}
        try: return json.loads(ln)
        except Exception: return {'id':req.get('id'),'status':'BAD_RESPONSE','error':ln[:400]}
    def close(self):
        try:
            self.proc.stdin.close(); self.proc.wait(timeout=5)
        except Exception: self._kill()
