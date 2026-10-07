"""Tests de jevbench.dgemma_f1: celdas congeladas, primera pasada caso a caso
(--limit 1, reglas evaluadas antes de cada caso), sesión persistente, lock,
pasada de reintento única y ciclo de vida del hijo — todo con hijo, health y
archivos simulados en un store.ROOT temporal."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from jevbench import dgemma_f1, store
from jevbench.battery import load_phase, questions_hash
from jevbench.dgemma_report import RUNS
from jevbench.redact import redact_options


def cell(**kw):
    c = {"run": "test_cell", "adapter": "systemone_http",
         "opts": {"url": "u", "extra": '{"a": 1}'},
         "phases": ["ood", "triage_es"], "health": ("h1", "h2"), "cap_min": 60}
    c.update(kw)
    return c


def meta_of(c, phase):
    qs, _ = load_phase(phase)
    return {"adapter": c["adapter"], "opts": redact_options(dict(c["opts"])),
            "questions_hash": questions_hash(qs)}


def full_cases(c, phase, errs=None):
    """Todos los casos intentados: respuesta o error. `errs`: {cid: mensaje}."""
    _, cases = load_phase(phase)
    extra = json.loads(c["opts"]["extra"]) if c["adapter"] == "systemone_http" else None
    recs = {}
    for cs in cases:
        if errs and cs.id in errs:
            recs[cs.id] = {"error": errs[cs.id]}
        else:
            rec = {"answers": {}, "ms": 10}
            if extra is not None:
                rec["raw"] = {"request": dict(extra)}
            recs[cs.id] = rec
    return recs


def doc_of(c, phase, errs=None, keep=None):
    recs = full_cases(c, phase, errs)
    if keep is not None:  # solo `keep` casos: fase parcial
        recs = {k: recs[k] for k in list(recs)[:keep]}
    return {"meta": meta_of(c, phase), "cases": recs}


class F1(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="f1_"))
        self._p = mock.patch.object(store, "ROOT", self.tmp)
        self._p.start()
        self.calls = []
        self.out = []
        (self.tmp / "logs").mkdir()

    def tearDown(self):
        self._p.stop()
        shutil.rmtree(self.tmp)

    def fake_runner(self, per_call, rc=0):
        """run_phase_command simulado: escribe el doc de la llamada y devuelve
        (rc, None). La primera pasada es caso a caso (--limit 1); el fake
        escribe el doc completo por llamada."""
        docs = iter(per_call)

        def fake(cmd, log, deadline):
            self.calls.append(cmd)
            doc = next(docs, None)
            if doc is not None:
                ph = cmd[cmd.index("--phases") + 1]
                run = cmd[cmd.index("--run") + 1]
                d = self.tmp / run
                d.mkdir(exist_ok=True)
                (d / f"{ph}.json").write_text(json.dumps(doc))
            return rc, None
        return mock.patch.object(dgemma_f1, "run_phase_command",
                                 side_effect=fake)

    def _run(self, c=None, **kw):
        kw.setdefault("session", "s1")
        kw.setdefault("printer", self.out.append)
        return dgemma_f1.run_cell(c or cell(), **kw)

    def _write_run(self, c, phases=None, errs=None):
        """Un run ya escrito (docs completos) + estado f1 coherente."""
        run_dir = self.tmp / c["run"]
        run_dir.mkdir(exist_ok=True)
        for ph in (phases or c["phases"]):
            (run_dir / f"{ph}.json").write_text(
                json.dumps(doc_of(c, ph, (errs or {}).get(ph))))
        return run_dir

    def _write_state(self, c, **kw):
        st = {"session": "s1", "adapter": c["adapter"], "opts": dict(c["opts"]),
              "phases": {}, "elapsed_s": 0.0, "intervals": [],
              "pass1_complete": True}
        st.update(kw)
        dgemma_f1.save_state(c["run"], st)
        return st

    # ---------------------------------------------------------- tabla
    def test_tabla_celdas(self):
        self.assertEqual({c["run"] for c in dgemma_f1.CELLS.values()}, set(RUNS.values()))
        # L (rev. 3) y L′ (rev. 4) quedan no ejecutables; L″ (rev. 5) ejecuta
        for name in ("Lp", "Ld", "Lp2", "Lr2", "Ld2"):
            self.assertFalse(dgemma_f1.CELLS[name].get("executable", True))
        for name in ("Lp3", "Lr3", "Ld3"):
            c = dgemma_f1.CELLS[name]
            self.assertTrue(c.get("executable", True))
            self.assertNotIn("extra_body", c["opts"])     # sin extra_body, rev. 4/5
            self.assertEqual(c["python"], dgemma_f1.VENV_LLM)
            self.assertEqual(c["opts"]["provider"], "openai")
            self.assertEqual(c["opts"]["base_url"], "http://127.0.0.1:18020/v1")
        self.assertEqual(dgemma_f1.CELLS["Lr3"]["phases"], ["papers32", "adv3"])
        self.assertEqual(dgemma_f1.CELLS["Ld3"]["opts"]["mode"], "discrete")
        self.assertEqual(dgemma_f1.CELLS["Lp3"]["cap_min"], 90)

    def test_celda_no_ejecutable(self):
        self.assertEqual(self._run(dgemma_f1.CELLS["Lp"]), 1)
        self.assertIn("no ejecutable", " ".join(self.out))

    # ---------------------------------------------------------- sesión/lock
    def test_sin_session_aborta(self):
        self.assertEqual(self._run(session=None), 1)

    def test_segundo_proceso_lock_aborta(self):
        lock = self.tmp / "logs" / "test_cell.f1.lock"
        lock.write_text("pid otro")
        self.assertEqual(self._run(), 1)
        self.assertIn("otro proceso tiene el run", " ".join(self.out))
        lock.unlink(missing_ok=True)

    def test_run_existente_sin_resume_aborta(self):
        c = cell()
        self._write_run(c)
        self._write_state(c)
        self.assertEqual(self._run(), 1)
        self.assertIn("--resume", " ".join(self.out))

    def test_resume_sesion_distinta_aborta(self):
        c = cell()
        self._write_run(c)
        self._write_state(c)
        self.assertEqual(self._run(resume=True, session="otra"), 1)
        self.assertIn("no mezcla sesiones", " ".join(self.out))

    def test_resume_opts_distintas_aborta(self):
        c = cell()
        run_dir = self._write_run(c)
        self._write_state(c)
        doc = json.loads((run_dir / "ood.json").read_text())
        doc["meta"]["opts"]["url"] = "otra"
        (run_dir / "ood.json").write_text(json.dumps(doc))
        self.assertEqual(self._run(resume=True), 1)
        self.assertIn("configuración congelada", " ".join(self.out))

    def test_resume_questions_hash_distinto_aborta(self):
        c = cell()
        run_dir = self._write_run(c)
        self._write_state(c)
        doc = json.loads((run_dir / "ood.json").read_text())
        doc["meta"]["questions_hash"] = "cambiado"
        (run_dir / "ood.json").write_text(json.dumps(doc))
        self.assertEqual(self._run(resume=True), 1)

    def test_resume_sin_estado_aborta(self):
        c = cell()
        self._write_run(c)  # sin .f1_state.json
        self.assertEqual(self._run(resume=True), 1)
        self.assertIn("f1_state", " ".join(self.out))

    # ---------------------------------------------------------- primera pasada
    def test_primera_pasada_completa_marca_estado(self):
        c = cell()
        docs = [doc_of(c, "ood"), doc_of(c, "triage_es")]
        with self.fake_runner(docs):
            self.assertEqual(self._run(), 0)
        st = dgemma_f1.load_state("test_cell")
        self.assertTrue(st["pass1_complete"])
        self.assertEqual(st["session"], "s1")
        self.assertEqual(st["phases"]["ood"]["questions_hash"], meta_of(c, "ood")["questions_hash"])
        self.assertEqual(len(self.calls), 2)

    def test_fase_parcial_no_declara_completa(self):
        c = cell()
        docs = [doc_of(c, "ood", keep=2)]  # falta el 3.º caso
        with self.fake_runner(docs):
            self.assertEqual(self._run(), 2)
        self.assertIn("no escribió ningún caso", " ".join(self.out))

    def test_rc_no_cero_para(self):
        c = cell()
        with self.fake_runner([doc_of(c, "ood")], rc=1):
            self.assertEqual(self._run(), 2)
        self.assertIn("rc=1", " ".join(self.out))

    # ---------------------------------------------------------- reglas de parada
    def test_parada_3_errores_fase(self):
        c = cell()
        _, cases = load_phase("ood")
        errs = {cs.id: "boom" for cs in cases}
        with self.fake_runner([doc_of(c, "ood", errs=errs)]):
            self.assertEqual(self._run(), 2)
        self.assertEqual(len(self.calls), 1)      # no lanza la 2.ª fase
        self.assertIn("3 errores en una fase", " ".join(self.out))

    def test_parada_10_errores_run(self):
        c = cell(phases=["ood", "triage_es", "triage_en", "papers32", "adv1"])
        docs = []
        for ph in c["phases"]:
            _, cases = load_phase(ph)
            errs = {cs.id: "boom" for cs in cases[:2]}   # 2 por fase < 3
            docs.append(doc_of(c, ph, errs=errs))
        with self.fake_runner(docs):
            self.assertEqual(self._run(c), 2)
        self.assertEqual(len(self.calls), 5)      # 5×2 = 10 errores
        self.assertIn("10 errores acumulados", " ".join(self.out))

    def test_timeout_health_cae_para(self):
        c = cell()
        errs = {load_phase("ood")[1][0].id: "timeout tras 120 s"}
        with self.fake_runner([doc_of(c, "ood", errs=errs)]), \
             mock.patch.object(dgemma_f1, "wait_health", return_value=(False, {})):
            self.assertEqual(self._run(), 2)
        self.assertIn("health", " ".join(self.out))
        self.assertEqual(len(self.calls), 1)

    def test_timeout_health_ok_continua_siguiente_caso(self):
        # tras health ok se continúa con el siguiente caso (la fase no se
        # relanza entera): el error persiste para el reintento
        c = cell()
        cid = load_phase("ood")[1][0].id
        health = mock.patch.object(dgemma_f1, "wait_health",
                                   return_value=(True, {}))
        with self.fake_runner([doc_of(c, "ood", errs={cid: "timeout"}),
                               doc_of(c, "triage_es")]), health as wh:
            self.assertEqual(self._run(), 0)
        self.assertEqual(wh.call_count, 1)
        # una invocación --limit 1 para ood (su doc quedó completo con el error)
        # y otra para triage_es
        self.assertEqual(len(self.calls), 2)
        self.assertIn("--limit", self.calls[0])

    def test_tope_global_ya_consumido(self):
        c = cell(cap_min=60)
        self._write_run(c, phases=["ood"])
        self._write_state(c, elapsed_s=3700, pass1_complete=False)
        with self.fake_runner([]):
            self.assertEqual(self._run(resume=True), 2)
        self.assertIn("tope", " ".join(self.out))
        self.assertEqual(len(self.calls), 0)

    def test_elapsed_s_se_acumula_en_el_estado(self):
        c = cell()
        docs = [doc_of(c, "ood"), doc_of(c, "triage_es")]
        with self.fake_runner(docs):
            self.assertEqual(self._run(), 0)
        st1 = dgemma_f1.load_state("test_cell")
        self.assertGreater(st1["elapsed_s"], 0)
        self.assertEqual(len(st1["intervals"]), 1)
        with self.fake_runner([]):
            self._run(resume=True)
        st2 = dgemma_f1.load_state("test_cell")
        self.assertGreaterEqual(st2["elapsed_s"], st1["elapsed_s"])
        self.assertEqual(len(st2["intervals"]), 2)

    # ---------------------------------------------------------- retry-pass
    def test_retry_pass_copia_y_reintenta_solo_errores(self):
        c = cell()
        cid = load_phase("ood")[1][0].id
        self._write_run(c, errs={"ood": {cid: "boom"}})
        self._write_state(c)
        with self.fake_runner([doc_of(c, "ood")]):  # retry lo repara
            self.assertEqual(self._run(retry_pass=True), 0)
        self.assertTrue((self.tmp / "test_cell_pass1").is_dir())
        self.assertEqual(len(self.calls), 1)      # solo ood tenía errores
        self.assertIn("--retry-errors", self.calls[0])
        self.assertNotIn("--limit", self.calls[0])
        st = dgemma_f1.load_state("test_cell")
        self.assertEqual(st["retry_scheduled"], {"ood": [cid]})
        self.assertEqual(st["retry_attempted"], {"ood": [cid]})
        self.assertNotIn("retry_not_attempted", st)

    def test_retry_timeout_no_duplica_reintento(self):
        # timeout en el reintento: health ok → NO se relanza; el cid queda con
        # su error y cada cid se reintenta exactamente una vez
        c = cell()
        cid = load_phase("ood")[1][0].id
        self._write_run(c, errs={"ood": {cid: "timeout tras 120 s"}})
        self._write_state(c)
        health = mock.patch.object(dgemma_f1, "wait_health",
                                   return_value=(True, {}))
        # el reintento vuelve a fallar con timeout, pero el registro cambia (ms)
        doc = doc_of(c, "ood", errs={cid: "timeout tras 120 s"})
        doc["cases"][cid]["ms"] = 5
        with self.fake_runner([doc]), health as wh:
            self.assertEqual(self._run(retry_pass=True), 0)
        self.assertEqual(len(self.calls), 1)      # no hay segunda invocación
        self.assertEqual(wh.call_count, 1)
        st = dgemma_f1.load_state("test_cell")
        self.assertEqual(st["retry_attempted"], {"ood": [cid]})

    def test_retry_rc1_sin_escribir_no_acredita_intentos(self):
        # rc=1 sin escribir nada: los cids programados no son intentos reales
        c = cell()
        _, casos = load_phase("ood")
        c1, c2 = casos[0].id, casos[1].id
        self._write_run(c, errs={"ood": {c1: "boom", c2: "boom"}})
        self._write_state(c)
        with self.fake_runner([], rc=1):          # el hijo falla sin escribir
            self.assertEqual(self._run(retry_pass=True), 2)
        st = dgemma_f1.load_state("test_cell")
        self.assertEqual(st["retry_scheduled"]["ood"], sorted([c1, c2]))
        self.assertEqual(st["retry_attempted"]["ood"], [])
        self.assertEqual(st["retry_not_attempted"]["ood"], sorted([c1, c2]))
        self.assertNotIn("retried", st)

    def test_retry_corte_a_mitad(self):
        # el hijo se corta tras el primer cid: solo él cambia de registro
        c = cell()
        _, casos = load_phase("ood")
        c1, c2 = casos[0].id, casos[1].id
        self._write_run(c, errs={"ood": {c1: "boom", c2: "boom"}})
        self._write_state(c)
        doc = doc_of(c, "ood")                     # c1 reparada (respuesta)
        doc["cases"][c2] = {"error": "boom"}       # c2 intacto: no intentado
        with self.fake_runner([doc]):
            self.assertEqual(self._run(retry_pass=True), 0)
        st = dgemma_f1.load_state("test_cell")
        self.assertEqual(st["retry_attempted"]["ood"], [c1])
        self.assertEqual(st["retry_not_attempted"]["ood"], [c2])

    def test_retry_timeout_health_cae_para(self):
        c = cell()
        cid = load_phase("ood")[1][0].id
        self._write_run(c, errs={"ood": {cid: "timeout tras 120 s"}})
        self._write_state(c)
        health = mock.patch.object(dgemma_f1, "wait_health",
                                   return_value=(False, {}))
        with self.fake_runner([doc_of(c, "ood", errs={cid: "timeout tras 120 s"})],
                              ), health:
            self.assertEqual(self._run(retry_pass=True), 2)
        self.assertIn("health", " ".join(self.out))

    def test_retry_pass_sin_marcador_aborta(self):
        c = cell()
        self._write_run(c)
        self._write_state(c, pass1_complete=False)
        self.assertEqual(self._run(retry_pass=True), 1)
        self.assertIn("primera pasada incompleta", " ".join(self.out))

    def test_retry_pass_fase_parcial_aborta(self):
        c = cell()
        run_dir = self._write_run(c)
        self._write_state(c)
        (run_dir / "triage_es.json").write_text(json.dumps(doc_of(c, "triage_es", keep=3)))
        self.assertEqual(self._run(retry_pass=True), 1)
        self.assertIn("sin intentar", " ".join(self.out))

    def test_retry_pass_fase_ausente_aborta(self):
        c = cell()
        run_dir = self._write_run(c)
        self._write_state(c)
        (run_dir / "triage_es.json").unlink()
        self.assertEqual(self._run(retry_pass=True), 1)

    def test_retry_pass_unico(self):
        c = cell()
        self._write_run(c)
        self._write_state(c)
        (self.tmp / "test_cell_pass1").mkdir()
        self.assertEqual(self._run(retry_pass=True), 1)
        self.assertIn("única", " ".join(self.out))

    # ---------------------------------------------------------- dry-run
    def test_dry_run_primera_pasada(self):
        self.assertEqual(self._run(dry_run=True, session=None), 0)
        text = "\n".join(self.out)
        self.assertIn("jevbench.run", text)
        self.assertNotIn("retry", text)
        self.assertNotIn("--retry-errors", text)

    def test_dry_run_retry_muestra_solo_reintento(self):
        self.assertEqual(self._run(dry_run=True, retry_pass=True, session=None), 0)
        text = "\n".join(self.out)
        self.assertIn("_pass1", text)
        # solo el modo reintento: todo comando lleva --retry-errors, ninguno es de 1.ª pasada
        cmds = [l for l in text.splitlines() if "jevbench.run" in l]
        self.assertTrue(cmds)
        self.assertTrue(all("--retry-errors" in l for l in cmds))


class _Proc:
    """Hijo simulado que nunca termina por sí solo."""
    def __init__(self):
        self.calls = []
        self.returncode = -9

    def poll(self):
        return None

    def terminate(self):
        self.calls.append("terminate")

    def wait(self, *a):
        self.calls.append("wait")
        return 0

    def kill(self):
        self.calls.append("kill")


class CicloDeVidaHijo(unittest.TestCase):
    """R4 hallazgo 4: ante excepción o KeyboardInterrupt del supervisor,
    run_phase_command termina y espera al hijo antes de propagar."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="f1_proc_"))
        self.log = self.tmp / "x.log"

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def _run_cmd(self, exc):
        proc = _Proc()
        with mock.patch.object(dgemma_f1.subprocess, "Popen", return_value=proc), \
             mock.patch.object(dgemma_f1.time, "sleep", side_effect=exc):
            with self.assertRaises(type(exc)):
                dgemma_f1.run_phase_command(["cmd"], self.log,
                                            dgemma_f1.time.monotonic() + 9999)
        return proc

    def test_excepcion_termina_al_hijo(self):
        proc = self._run_cmd(RuntimeError("boom"))
        self.assertIn("terminate", proc.calls)
        self.assertIn("wait", proc.calls)

    def test_keyboardinterrupt_termina_al_hijo(self):
        proc = self._run_cmd(KeyboardInterrupt())
        self.assertIn("terminate", proc.calls)
        self.assertIn("wait", proc.calls)


if __name__ == "__main__":
    unittest.main()
