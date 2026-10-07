"""Tests de jevbench.dgemma_gate con extractos sintéticos en el formato real del
log de vLLM 1b3b88ec (líneas DEBUG `Request <id> details: prompt: %r,
prompt_token_ids: …` e INFO `Received request <id>: params: SamplingParams(…,
extra_args={'diffusion_canvas_length': N, …})`)."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from jevbench import dgemma_gate
from jevbench.battery import load_phase, questions_hash
from jevbench.dgemma_preflight import sha
from jevbench.rotation import rotate_choice

FAKE_SERVER = (
    "def jev_schema(body):\n"
    "    return {'questions': body['questions']}\n"
    "def system_text(schema):\n"
    "    return 'SYS::' + '|'.join(schema['questions'])\n")

P = "|"  # el prompt del log lleva los marcadores de la plantilla de chat


def sys_text_of(qs):
    return "SYS::" + "|".join(qs)


def log_req(rid, sys_text, state, n_ids=100, width=32, ts="10-06 08:50:03",
            details=True, bad_repr=False):
    """Las dos líneas enlazadas por `chatcmpl-…` en el formato real."""
    lines = []
    if details:
        prompt = (f"<{P}turn>system\n{sys_text} <turn{P}>\n"
                  f"<{P}turn>user\n{state}<turn{P}>\n<{P}turn>model\n")
        rep = bad_repr if bad_repr else repr(prompt)
        lines.append(f"(APIServer pid=1) DEBUG {ts} [request_logger.py:53] "
                     f"Request {rid} details: prompt: {rep}, "
                     f"prompt_token_ids: {list(range(n_ids))}, "
                     "prompt_embeds shape: None.")
    lines.append(f"(APIServer pid=1) INFO {ts} [request_logger.py:63] "
                 f"Received request {rid}: params: SamplingParams(max_tokens=11, "
                 f"extra_args={{'diffusion_canvas_length': {width}, "
                 "'diffusion_max_steps': 1}), lora_request: None.")
    return "\n".join(lines)


class Gate(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="gate_"))
        self.qs, self.cases = load_phase("ood")
        self.c = self.cases[0]
        self.hash = questions_hash(self.qs)
        self.sys_text = sys_text_of(self.qs)
        self.srv = self.tmp / "structured_server_frozen.py"
        self.srv.write_text(FAKE_SERVER)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def _preflight(self, rotate=0, width=32):
        qs = rotate_choice(self.qs, rotate) if rotate else self.qs
        return {"canvas": 64, "rotate": rotate, "cases": 195,
                "server_sha256": sha(self.srv.read_bytes()),
                "prompt_tokens": {"ood:c1": 100},
                "families": {self.hash: {
                    "phases": ["ood"],
                    "by_canvas": {"64": {"fits": True, "width": width, "stages": 1,
                                         "groups": 1, "template_tokens": 17,
                                         "system_text": sys_text_of(qs)}}}}}

    def _results(self, state=None, qs=None, reads=1, pt=100, meta=None, cases=None,
                 cid="c1", stage_err=None):
        req = {"state": state if state is not None else self.c.state,
               "questions": qs if qs is not None else self.qs, "samples": "auto"}
        diag = {"prompt_tokens": pt, "samples": {"n": reads},
                "stages": [{"name": "s0"}], "chunks": [{"id": "g0"}],
                "skipped": [], "timing": {"total_ms": 8}}
        if stage_err:
            diag.update(stage_err)
        rec = {"answers": {"clinical": {"noul": 0.4}}, "ms": 10,
               "raw": {"request": req, "response": {"diagnostics": diag}}}
        doc = {"meta": {"adapter": "systemone_http",
                        "questions_hash": self.hash, **(meta or {})},
               "cases": cases if cases is not None else {cid: rec}}
        f = self.tmp / "ood.json"
        f.write_text(json.dumps(doc))
        return f

    def _evaluate(self, results=None, log="", rotate=0, preflight=None, **kw):
        f = results or self._results()
        pf = preflight or self._preflight(rotate=rotate)
        mod, err, fatal = dgemma_gate.load_frozen_server(
            self.srv, sha(self.srv.read_bytes()))
        return dgemma_gate.evaluate([f], pf, log,
                                    ss=mod, ss_error=err, ss_fatal=fatal, **kw)

    def _log_ok(self, n_req=1, **kw):
        return "\n".join(
            log_req(f"chatcmpl-{i:03d}", self.sys_text, self.c.state, **kw)
            for i in range(n_req))

    def test_caso_ok(self):
        res = self._evaluate(log=self._log_ok())
        self.assertTrue(res["ok"], json.dumps(res["checks"], indent=1)[:4000])

    def test_cero_casos_cierra(self):
        res = self._evaluate(results=self._results(cases={}), log=self._log_ok())
        self.assertFalse(res["ok"])
        self.assertTrue(any("ningún caso" in d for d in res["checks"][4]["detalles"]))

    def test_rot1_contra_preflight_base_falla(self):
        f = self._results(qs=rotate_choice(self.qs, 1), meta={"rotate_choice": 1})
        res = self._evaluate(results=f, log=self._log_ok())
        self.assertFalse(res["ok"])
        self.assertTrue(any("rotate_choice=1" in d for d in res["checks"][3]["detalles"]))

    def test_rot1_con_su_preflight_ok(self):
        qs1 = rotate_choice(self.qs, 1)
        f = self._results(qs=qs1, meta={"rotate_choice": 1})
        log = log_req("chatcmpl-000", sys_text_of(qs1), self.c.state)
        res = self._evaluate(results=f, log=log, rotate=1)
        self.assertTrue(res["ok"], json.dumps(res["checks"], indent=1)[:4000])

    def test_calentamiento_ok_peticion_actual_ancho_mal(self):
        # el warmup correcto (32) no "lava" el ancho 64 de la petición actual
        log = (log_req("chatcmpl-warm", self.sys_text, "texto de calentamiento",
                       width=32, ts="10-06 08:00:00")
               + "\n" + log_req("chatcmpl-000", self.sys_text, self.c.state,
                                width=64, ts="10-06 08:50:03"))
        res = self._evaluate(log=log)
        self.assertFalse(res["ok"])
        self.assertTrue(any("ancho 64" in d for d in res["checks"][2]["detalles"]))

    def test_sistema_con_separadores_cambiados_falla(self):
        # mismo sistema pero con los '|' sustituidos por espacios (whitespace)
        log = log_req("chatcmpl-000", self.sys_text.replace("|", " "), self.c.state)
        res = self._evaluate(log=log)
        self.assertFalse(res["ok"])
        self.assertTrue(any("ninguna petición atribuida" in d
                            for d in res["checks"][0]["detalles"]))

    def test_log_solo_info_evidencia_insuficiente(self):
        log = log_req("chatcmpl-000", "", self.c.state, details=False)
        res = self._evaluate(log=log)
        self.assertFalse(res["ok"])
        self.assertTrue(any("prompt no registrado" in d
                            for d in res["checks"][0]["detalles"]))

    def test_repr_no_decodificable_cierra(self):
        log = log_req("chatcmpl-000", self.sys_text, self.c.state,
                      bad_repr="'prompt sin cerrar")
        res = self._evaluate(log=log)
        self.assertFalse(res["ok"])
        self.assertTrue(any("no decodificable" in d
                            for d in res["checks"][0]["detalles"]))

    def test_reads_no_igualan_peticiones(self):
        res = self._evaluate(log=self._log_ok(n_req=1),
                             results=self._results(reads=3))
        self.assertFalse(res["ok"])
        self.assertIn("3 lecturas", json.dumps(res["checks"], ensure_ascii=False))
        res = self._evaluate(log=self._log_ok(n_req=3),
                             results=self._results(reads=3))
        self.assertTrue(res["ok"], json.dumps(res["checks"], indent=1)[:4000])

    def test_mismo_state_otro_sistema_conflicto(self):
        log = (self._log_ok() + "\n"
               + log_req("chatcmpl-099", "SYS::otro|sistema", self.c.state))
        res = self._evaluate(log=log)
        self.assertFalse(res["ok"])
        self.assertTrue(any("mismo state y otro sistema" in d
                            for d in res["checks"][0]["detalles"]))

    def test_since_excluye_el_calentamiento(self):
        log = (log_req("chatcmpl-warm", self.sys_text, self.c.state,
                       ts="10-06 08:00:00", width=64)
               + "\n" + log_req("chatcmpl-000", self.sys_text, self.c.state,
                                ts="10-06 08:50:03"))
        res = self._evaluate(log=log)
        self.assertFalse(res["ok"])  # reads=1 pero 2 peticiones atribuidas
        res = self._evaluate(log=log, since="10-06 08:40:00")
        self.assertTrue(res["ok"], json.dumps(res["checks"], indent=1)[:4000])

    def test_sin_server_no_certifica(self):
        res = dgemma_gate.evaluate([self._results()], self._preflight(),
                                   self._log_ok(), ss=None, ss_error=None)
        self.assertFalse(res["ok"])
        self.assertTrue(any("no certifica" in d for d in res["checks"][3]["detalles"]))

    def test_require_families_all(self):
        # preflight con las tres familias; solo ood tiene casos verificados
        pre = self._preflight()
        for ph in ("triage_es", "papers32"):
            qs2, _ = load_phase(ph)
            pre["families"][questions_hash(qs2)] = {
                "phases": [ph],
                "by_canvas": {"64": {"fits": True, "width": 32, "stages": 1,
                                     "groups": 1, "template_tokens": 17,
                                     "system_text": sys_text_of(qs2)}}}
        mod, err, fatal = dgemma_gate.load_frozen_server(
            self.srv, sha(self.srv.read_bytes()))
        res = dgemma_gate.evaluate([self._results()], pre, self._log_ok(),
                                   ss=mod, ss_error=err, ss_fatal=fatal,
                                   require_families="all")
        self.assertFalse(res["ok"])
        faltan = [d for d in res["checks"][4]["detalles"] if "sin ningún caso" in d]
        self.assertEqual(len(faltan), 2)  # triaje y papers32
        res = dgemma_gate.evaluate([self._results()], pre, self._log_ok(),
                                   ss=mod, ss_error=err, ss_fatal=fatal)
        self.assertTrue(res["ok"], json.dumps(res["checks"], indent=1)[:4000])

    def test_token_ids_desigual_prompt_tokens(self):
        log = log_req("chatcmpl-000", self.sys_text, self.c.state, n_ids=90)
        res = self._evaluate(log=log)
        self.assertFalse(res["ok"])
        self.assertTrue(any("token ids" in d for d in res["checks"][1]["detalles"]))

    def test_dos_grupos_cierra(self):
        f = self._results(stage_err={"chunks": [{"id": "g0"}, {"id": "g1"}]})
        res = self._evaluate(results=f, log=self._log_ok())
        self.assertFalse(res["ok"])

    def test_ventana_por_lineas_dos_ejecuciones(self):
        # R4 hallazgo 1: mismo log con ejecución base y Rot1 sobre los mismos
        # estados; --log-from/--log-to las separa (cada registro = 2 líneas)
        qs1 = rotate_choice(self.qs, 1)
        bloque_base = log_req("chatcmpl-b0", self.sys_text, self.c.state)
        bloque_rot = log_req("chatcmpl-r0", sys_text_of(qs1), self.c.state)
        log = bloque_base + "\n" + bloque_rot
        n_base = len(bloque_base.splitlines())
        # sin ventana: la petición Rot1 es un conflicto "mismo state, otro sistema"
        res = self._evaluate(log=log)
        self.assertFalse(res["ok"])
        # ventana base (líneas 1..n_base): pasa y registra los límites usados
        res = self._evaluate(log=log, log_from=1, log_to=n_base)
        self.assertTrue(res["ok"], json.dumps(res["checks"], indent=1)[:4000])
        self.assertEqual(res["ventana"]["log_from"], 1)
        self.assertEqual(res["ventana"]["log_to"], n_base)
        self.assertEqual(res["ventana"]["excluidos"], 1)
        # ventana Rot1 (resto del log) con su preflight rotate=1: también pasa
        f_rot = self._results(qs=qs1, meta={"rotate_choice": 1})
        res = self._evaluate(results=f_rot, log=log, rotate=1,
                             log_from=n_base + 1)
        self.assertTrue(res["ok"], json.dumps(res["checks"], indent=1)[:4000])
        # ventana que parte un registro a medias: la línea INFO queda fuera y el
        # registro no entra → sin petición atribuida
        res = self._evaluate(log=log, log_to=n_base - 1)
        self.assertFalse(res["ok"])
        self.assertTrue(any("ninguna petición atribuida" in d
                            for d in res["checks"][0]["detalles"]))

    # -------------------------------------------------- numeración física LF
    def test_progreso_con_cr_no_rompe_numeracion(self):
        # R6 hallazgo 1: barras de progreso con \r delante de una petición en la
        # misma línea física no rompen el parseo ni numeran líneas extra
        log = ("progreso 10%\rprogreso 20%\r"
               + log_req("chatcmpl-000", self.sys_text, self.c.state))
        recs = dgemma_gate.parse_log(log)
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0]["lines"], [1, 2])       # los \r no cuentan
        self.assertIn(self.sys_text, recs[0]["prompt"])
        res = self._evaluate(log=log)
        self.assertTrue(res["ok"], json.dumps(res["checks"], indent=1)[:4000])

    def test_detalles_y_recibido_misma_linea_fisica(self):
        # DEBUG e INFO separados por \r en una única línea física: el registro
        # conserva prompt, ancho y el mismo número de línea
        prompt = (f"<{P}turn>system\n{self.sys_text} <turn{P}>\n"
                  f"<{P}turn>user\n{self.c.state}<turn{P}>\n<{P}turn>model\n")
        log = (f"(APIServer pid=1) DEBUG 10-06 08:50:03 [x] Request chatcmpl-000 "
               f"details: prompt: {prompt!r}, prompt_token_ids: [1, 2], "
               "prompt_embeds shape: None.\r"
               f"(APIServer pid=1) INFO 10-06 08:50:03 [x] Received request "
               "chatcmpl-000: params: SamplingParams(extra_args="
               "{'diffusion_canvas_length': 32}), lora_request: None.")
        recs = dgemma_gate.parse_log(log)
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0]["lines"], [1, 1])
        self.assertEqual(recs[0]["width"], 32)
        self.assertIn(self.sys_text, recs[0]["prompt"])

    def test_extracto_sed_con_relleno_reproduce(self):
        # la ventana A..B (líneas físicas, como `wc -l`/`sed -n`) reproduce la
        # puerta desde `sed -n A,Bp` + A-1 líneas vacías de relleno
        bloque_warm = log_req("chatcmpl-w0", self.sys_text, self.c.state,
                              width=64, ts="10-06 08:00:00")
        bloque_run = log_req("chatcmpl-000", self.sys_text, self.c.state)
        log = bloque_warm + "\n" + bloque_run + "\ncola\n"
        lineas = log.split("\n")
        a = len(bloque_warm.split("\n")) + 1             # primera línea del run
        b = a + len(bloque_run.split("\n")) - 1          # última línea del run
        res_orig = self._evaluate(log=log, log_from=a, log_to=b)
        self.assertTrue(res_orig["ok"],
                        json.dumps(res_orig["checks"], indent=1)[:4000])
        # sin ventana, el warmup (mismo state, ancho mal) cerraría la puerta
        self.assertFalse(self._evaluate(log=log)["ok"])
        extracto = "\n" * (a - 1) + "\n".join(lineas[a - 1:b])
        res_ext = self._evaluate(log=extracto, log_from=a, log_to=b)
        self.assertEqual(res_ext["ok"], res_orig["ok"])
        self.assertEqual(res_ext["verificados"], res_orig["verificados"])
        # los mismos registros dentro de la ventana en ambos ficheros
        self.assertEqual(res_ext["ventana"]["registros"],
                         res_orig["ventana"]["registros"])

    # --------------------------------------- casos con estado idéntico (C7)
    def _rec(self, reads):
        req = {"state": self.c.state, "questions": self.qs, "samples": "auto"}
        diag = {"prompt_tokens": 100, "samples": {"n": reads},
                "stages": [{"name": "s0"}], "chunks": [{"id": "g0"}],
                "skipped": [], "timing": {"total_ms": 8}}
        return {"answers": {"clinical": {"noul": 0.4}}, "ms": 10,
                "raw": {"request": req, "response": {"diagnostics": diag}}}

    def test_mismo_state_recuento_conjunto(self):
        # F1 real: papers32 P02/P03 comparten state → atribución conjunta
        cases = {"c1": self._rec(reads=1), "c2": self._rec(reads=4)}
        f = self._results(cases=cases)
        pf = self._preflight()
        pf["prompt_tokens"]["ood:c2"] = 100
        log5 = "\n".join(log_req(f"chatcmpl-{i:03d}", self.sys_text,
                                 self.c.state) for i in range(5))
        res = self._evaluate(results=f, log=log5, preflight=pf)
        self.assertTrue(res["ok"], json.dumps(res["checks"], indent=1)[:4000])
        det = json.dumps(res["checks"][0]["detalles"], ensure_ascii=False)
        self.assertIn("estado idéntico", det)
        self.assertIn("atribución conjunta", det)
        # una petición de más cierra la puerta para todo el grupo
        log6 = log5 + "\n" + log_req("chatcmpl-005", self.sys_text, self.c.state)
        res = self._evaluate(results=f, log=log6, preflight=pf)
        self.assertFalse(res["ok"])
        self.assertIn("lecturas en conjunto",
                      json.dumps(res["checks"], ensure_ascii=False))
        self.assertEqual(res["verificados"], 0)
        # un caso único sigue exigiendo su recuento exacto
        res = self._evaluate(log=self._log_ok(n_req=2))
        self.assertFalse(res["ok"])
        self.assertIn("2 petición(es) atribuidas ≠ 1 lecturas",
                      json.dumps(res["checks"], ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
