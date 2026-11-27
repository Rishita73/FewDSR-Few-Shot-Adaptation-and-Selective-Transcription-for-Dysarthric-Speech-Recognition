"""Smoke test of app.py against a STUB streamlit (streamlit is not installed in the authoring sandbox;
this does NOT prove the app renders in a browser)."""
import contextlib, json, os, runpy, shutil, sys, tempfile, types, unittest
from unittest import mock

from core import app_support as AS
from tests.fixtures_part3 import write_fixture

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Ctx:
    """Context manager / column stand-in; calls on it (e.g. column.metric) are logged too."""
    def __init__(self, log=None): self.log = log
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def __getattr__(self, n):
        def f(*a, **k):
            if self.log is not None:
                self.log.append((n, a, k))
            return Ctx(self.log)
        return f


def make_stub(log):
    st = types.ModuleType("streamlit")
    def rec(name, ret=None):
        def f(*a, **k):
            # DataFrame repr is avoided: pandas in some environments cannot repr str-dtype frames inside tuples
            a_safe = tuple(f"<DataFrame {x.shape}>" if hasattr(x, "shape") and hasattr(x, "columns") else x for x in a)
            log.append((name, a_safe, k)); return ret(*a, **k) if callable(ret) else (Ctx() if ret is None else ret)
        return f
    st.set_page_config = rec("set_page_config"); st.markdown = rec("markdown"); st.title = rec("title"); st.caption = rec("caption")
    for n in ("error", "warning", "info", "success", "code", "audio", "write", "json", "image", "pyplot", "dataframe", "subheader"):
        setattr(st, n, rec(n))
    st.tabs = lambda names: [Ctx() for _ in names]
    st.columns = lambda spec: [Ctx(log) for _ in (range(spec) if isinstance(spec, int) else spec)]
    st.expander = lambda *a, **k: Ctx()
    st.metric = rec("metric"); st.stop = lambda: (_ for _ in ()).throw(SystemExit("st.stop"))
    st.selectbox = lambda label, opts, *a, **k: list(opts)[0]
    st.radio = lambda label, opts, *a, **k: list(opts)[0]
    st.slider = lambda label, lo, hi, val=None, *a, **k: val if val is not None else lo
    st.button = lambda *a, **k: False
    st.file_uploader = lambda *a, **k: None
    st.cache_resource = lambda f: f
    st.sidebar = Ctx(); st.sidebar.header = rec("sb.header"); st.sidebar.warning = rec("sb.warning")
    st.sidebar.markdown = rec("sb.markdown"); st.sidebar.selectbox = st.selectbox; st.sidebar.slider = st.slider
    return st


class TestApp(unittest.TestCase):
    def run_app(self, results_dir=None):
        log = []
        with mock.patch.dict(sys.modules, {"streamlit": make_stub(log)}):
            # point the app's RESULTS at a temp dir by patching load_summary
            with mock.patch.object(AS, "load_summary", lambda d: AS_load(results_dir) if results_dir else None):
                runpy.run_path(os.path.join(ROOT, "app.py"), run_name="__main__")
        return log

    def test_starts_without_results_and_keeps_simulated_banner_and_empty_state(self):
        log = self.run_app(None)
        text = " ".join(str(a) for _, a, _ in log)
        self.assertIn("SIMULATED DEMO", text)
        self.assertIn("No experiment results yet", text)
        self.assertNotIn("TEST-FIXTURE", text)

    def test_renders_results_tab_from_summary_and_flags_fixture(self):
        from experiments import run_all
        tmp = tempfile.mkdtemp()
        try:
            raw, res = os.path.join(tmp, "raw"), os.path.join(tmp, "results")
            write_fixture(raw)
            with contextlib.redirect_stdout(open(os.devnull, "w")):
                run_all.main(["--raw", raw, "--out", res, "--adapters", os.path.join(tmp, "x"), "--boot", "50", "--fixture"])
            log = self.run_app(res)
            text = " ".join(str(a) for _, a, _ in log)
            self.assertIn("SIMULATED DEMO", text)                 # still there
            self.assertIn("TEST-FIXTURE", text)
            self.assertTrue(any(n == "metric" and "ECE" in a[0] for n, a, _ in log))
            self.assertNotIn("No experiment results yet", text)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


def AS_load(d):
    with open(os.path.join(d, "summary.json"), encoding="utf-8") as f:
        return json.load(f)


class TestSupport(unittest.TestCase):
    def test_condition_and_params(self):
        self.assertEqual(AS.condition_for_adapter(None), "baseline")
        self.assertEqual(AS.condition_for_adapter("F04_K10"), "lora_K10")
        with self.assertRaises(ValueError):
            AS.condition_for_adapter("weird")
        summ = {"deploy_params": {"baseline": {"T": 1.5, "gamma": 2.0, "tau": 0.8}, "lora_K5": {"T": 1.2, "gamma": None, "tau": 0.7}}}
        self.assertEqual(AS.params_for(summ, "baseline")[0], {"T": 1.5, "gamma": 2.0, "tau": 0.8})
        self.assertIsNone(AS.params_for(summ, "lora_K5")[0])          # incomplete -> not used
        self.assertIsNone(AS.params_for(summ, "lora_K10")[0])
        self.assertIsNone(AS.params_for(None, "baseline")[0])

    def test_adapter_options_require_adapter_config(self):
        tmp = tempfile.mkdtemp()
        try:
            for d, has in (("A_K5", True), ("B_K10", False)):
                os.makedirs(os.path.join(tmp, d))
                if has:
                    open(os.path.join(tmp, d, "adapter_config.json"), "w").write("{}")
            self.assertEqual(AS.adapter_options(tmp), ["A_K5"])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_torch_absent_is_reported_not_crashing(self):
        with mock.patch("importlib.util.find_spec", lambda n: None):
            self.assertFalse(AS.torch_available())


if __name__ == "__main__":
    unittest.main()
