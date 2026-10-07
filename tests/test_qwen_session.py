"""Tests del supervisor de la sesión Qwen3.8-27B FP8 (jevbench.qwen_session):
rotación selectiva de department, puertas por combinación, runner caso a caso
con reglas de parada y análisis pre-registrado — todo offline, con servidor
falso y datos sintéticos.

  .venv-llm/bin/python -m unittest tests.test_qwen_session -v
"""
import copy
import hashlib
import importlib.util
import json
import shutil
import subprocess
import tempfile
import unittest
from collections import UserDict
from pathlib import Path
from unittest import mock

import jevbench.qwen_session as qs_mod
from jevbench import metrics, score, store
from jevbench.battery import TRIAGE_QS, load_phase, questions_hash
from jevbench.rotation import (NAMED_ORDERS, order_manifest, reorder_choice,
                               resolve_choice_order, rotate_choice)

HAS_LIB = importlib.util.find_spec("system_one_adapter") is not None

ANSWERS = {"department": {"admin": 0.9, "bronchoscopia": 0.05,
                          "urgencias": 0.03, "consulta_externa": 0.02},
           "urgency": {"0": 0.8, "1": 0.15, "2": 0.05},
           "clinical": 0.1, "hostile": 0.0, "same_day": 0.2}
STATE = "Factura duplicada, pido reembolso."


class TmpStore(unittest.TestCase):
    """store.ROOT temporal por test."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="qs_"))
        self._p = mock.patch.object(store, "ROOT", self.tmp)
        self._p.start()
        (self.tmp / "logs").mkdir()

    def tearDown(self):
        self._p.stop()
        shutil.rmtree(self.tmp)


# -------------------------------------------------------------- rotación

class TestSelectiveOrder(unittest.TestCase):
    def test_named_orders_tabla_r13(self):
        self.assertEqual(NAMED_ORDERS["department"]["d0"],
                         ["bronchoscopia", "consulta_externa", "urgencias",
                          "admin"])
        # d1-d3 son las rotaciones cíclicas del orden canónico
        for k in (1, 2, 3):
            want = list(rotate_choice(
                {"department": {"type": "choice",
                                "criteria": dict.fromkeys(
                                    NAMED_ORDERS["department"]["d0"])}},
                k)["department"]["criteria"])
            self.assertEqual(NAMED_ORDERS["department"][f"d{k}"], want)

    def test_reorder_solo_department(self):
        qs = {"department": TRIAGE_QS["department"],
              "domain": {"type": "choice",
                         "criteria": {"a": "A", "b": "B", "c": "C"}},
              "urgency": TRIAGE_QS["urgency"]}
        out = reorder_choice(qs, {"department": ["urgencias", "admin",
                                                 "bronchoscopia",
                                                 "consulta_externa"]})
        self.assertEqual(list(out["department"]["criteria"]),
                         ["urgencias", "admin", "bronchoscopia",
                          "consulta_externa"])
        self.assertEqual(list(out["domain"]["criteria"]), ["a", "b", "c"])
        for k, v in TRIAGE_QS["department"]["criteria"].items():
            self.assertEqual(out["department"]["criteria"][k], v)

    def test_reorder_rejects_non_permutation(self):
        with self.assertRaises(ValueError):
            reorder_choice(TRIAGE_QS, {"department": ["admin", "admin"]})
        with self.assertRaises(ValueError):
            reorder_choice(TRIAGE_QS, {"urgency": ["0", "1", "2"]})

    def test_reorder_missing_qid_is_noop(self):
        """La misma spec aplica a las 11 fases: donde la pregunta no existe
        (papers32, ood) no hay nada que reordenar."""
        out = reorder_choice({"urgency": TRIAGE_QS["urgency"]},
                             {"department": NAMED_ORDERS["department"]["d1"]})
        self.assertEqual(list(out["urgency"]["criteria"]),
                         list(TRIAGE_QS["urgency"]["criteria"]))

    def test_resolve_choice_order(self):
        self.assertEqual(resolve_choice_order("department:d1"),
                         {"department": NAMED_ORDERS["department"]["d1"]})
        self.assertEqual(resolve_choice_order("department:a,b,c"),
                         {"department": ["a", "b", "c"]})
        for bad in ("department:", "department", ":", "department:d9"):
            with self.assertRaises(ValueError):
                resolve_choice_order(bad)

    def test_order_manifest(self):
        orders = {"department": NAMED_ORDERS["department"]["d2"]}
        qs_eff = reorder_choice(TRIAGE_QS, orders)
        m = order_manifest(qs_eff, orders)
        self.assertEqual(m["order"]["department"],
                         NAMED_ORDERS["department"]["d2"])
        self.assertIn("perm_sha256", m)
        m0 = order_manifest(TRIAGE_QS, {"department":
                                        NAMED_ORDERS["department"]["d0"]})
        self.assertEqual(m0["order"]["department"],
                         list(TRIAGE_QS["department"]["criteria"]))
        self.assertNotEqual(m["perm_sha256"], m0["perm_sha256"])


# ------------------------------------------------- adaptador choice_order

@unittest.skipUnless(HAS_LIB, "necesita system-one-adapter (.venv-llm)")
class TestAdapterChoiceOrder(unittest.TestCase):
    def _llm(self, server, **kw):
        from jevbench.adapters.llm import LLM
        return LLM(mode="probabilities", base_url=server.base_url,
                   model="fake-model", api_key="none", capture_raw=True,
                   timeout=5, case_timeout=20, **kw)

    def _plan(self):
        from tests.test_llm_adapter import _answers_payload, _chat_completion
        text = _answers_payload("probabilities", ANSWERS)
        return lambda n, body: {"json": _chat_completion(text)}

    def test_schema_reorders_only_department(self):
        from tests.test_llm_adapter import FakeOpenAIServer
        with FakeOpenAIServer(self._plan()) as server:
            model = self._llm(server, structured="true",
                              inject_schema_in_prompt="true",
                              choice_order="department:d1")
            model.decide(STATE, TRIAGE_QS)
        req = server.httpd.requests[0]["body"]
        sch = req["response_format"]["json_schema"]["schema"]
        ans = sch["properties"]["answers"]
        ans = sch["$defs"][ans["$ref"].split("/")[-1]]
        dept_ref = ans["properties"]["department"]["$ref"].split("/")[-1]
        self.assertEqual(list(sch["$defs"][dept_ref]["properties"]),
                         NAMED_ORDERS["department"]["d1"])
        # domain/design no están aquí; pero en una fase papers el resto de
        # choice tampoco rotaría: se verifica con TRIAGE_QS + una extra
        self.assertEqual(qs_mod.j67._embedded_schema(
            req["messages"][0]["content"]), sch)

    def test_reorder_leaves_other_choice_untouched(self):
        from tests.test_llm_adapter import FakeOpenAIServer, _chat_completion
        mixed = dict(TRIAGE_QS)
        mixed["domain"] = {"type": "choice", "instructions": "d?",
                           "criteria": {"a": "A", "b": "B", "c": "C"}}

        def plan(n, body):
            sch = body["response_format"]["json_schema"]["schema"]
            ans = sch["properties"]["answers"]
            ans = sch["$defs"][ans["$ref"].split("/")[-1]]
            out = {}
            for qid, field in ans["properties"].items():
                ref = (sch["$defs"][field["$ref"].split("/")[-1]]
                       if "$ref" in field else field)
                out[qid] = ({k: 0.0 for k in ref.get("properties", {})}
                            if ref.get("properties") else 0.0)
            return {"json": _chat_completion(
                json.dumps({"answers": out}))}
        with FakeOpenAIServer(plan) as server:
            model = self._llm(server, structured="true",
                              inject_schema_in_prompt="true",
                              choice_order="department:d3")
            model.decide(STATE, mixed)
        sch = (server.httpd.requests[0]["body"]["response_format"]
               ["json_schema"]["schema"])
        ans = sch["properties"]["answers"]
        ans = sch["$defs"][ans["$ref"].split("/")[-1]]
        dom = ans["properties"]["domain"]
        dom = sch["$defs"][dom["$ref"].split("/")[-1]] if "$ref" in dom else dom
        self.assertEqual(list(dom["properties"]), ["a", "b", "c"])

    def test_literal_label_intact(self):
        """El literal del modelo mapea a la etiqueta original con cualquier
        orden: la respuesta {'admin': .9, ...} decide 'admin'."""
        from tests.test_llm_adapter import FakeOpenAIServer
        for order in ("d0", "d2"):
            with FakeOpenAIServer(self._plan()) as server:
                model = self._llm(server, structured="true",
                                  inject_schema_in_prompt="true",
                                  choice_order=f"department:{order}")
                out = model.decide(STATE, TRIAGE_QS)
            self.assertEqual(out["answers"]["department"]["choice"], "admin")

    def test_choice_order_excluye_rotate(self):
        from jevbench.adapters.llm import LLM
        with self.assertRaises(ValueError):
            LLM(mode="probabilities", base_url="http://127.0.0.1:9/v1",
                api_key="none", choice_order="department:d1", rotate_choice=1)

    def test_expected_sha_depends_on_order(self):
        from jevbench.adapters.llm import LLM
        kw = dict(mode="probabilities", structured="true",
                  inject_schema_in_prompt="true",
                  base_url="http://127.0.0.1:9/v1", api_key="none")
        a = LLM(**kw, choice_order="department:d0")
        b = LLM(**kw, choice_order="department:d1")
        self.assertNotEqual(a.expected_system_prompt_sha256(TRIAGE_QS),
                            b.expected_system_prompt_sha256(TRIAGE_QS))
        c = LLM(**kw)
        self.assertEqual(a.expected_system_prompt_sha256(TRIAGE_QS),
                         c.expected_system_prompt_sha256(TRIAGE_QS))


# --------------------------------------------------------------- refs (F1)

class _TokNested:
    """Tokenizer stub: honra enable_thinking por chat_template_kwargs."""
    chat_template = "tpl-stub"

    def apply_chat_template(self, messages, add_generation_prompt=True,
                            tokenize=True, **kw):
        th = (kw.get("chat_template_kwargs") or {}).get("enable_thinking")
        n = 3 if th else 1
        return "x" * n if not tokenize else list(range(n))


class _TokBatchDict:
    """Tokenizer stub con el contrato de transformers 5.x: ignora
    return_dict=False y devuelve siempre un mapping tipo BatchEncoding
    (input_ids + attention_mask). len() del retorno sería 2 — las
    CLAVES —, no los tokens (defecto D1-A)."""
    chat_template = "tpl-batches"

    def apply_chat_template(self, messages, add_generation_prompt=True,
                            tokenize=True, **kw):
        th = (kw.get("chat_template_kwargs") or {}).get("enable_thinking")
        n = 5 if th else 2
        if not tokenize:
            return "y" * n
        return UserDict({"input_ids": list(range(n)),
                         "attention_mask": [1] * n})


class TestRefs(TmpStore):
    def test_thinking_form_detecta_flag_ignorado(self):
        """R16 §1: una plantilla con **kwargs que lee enable_thinking
        directamente ignora la forma anidada sin excepción (render idéntico
        on/off); refs usa la forma que de verdad cambia el render y aborta
        si ninguna lo hace."""

        class DirectOnly:
            def apply_chat_template(self, messages, enable_thinking=True,
                                    tokenize=False, **kw):
                if tokenize:
                    return [0, 0] if enable_thinking else [0]
                return "on" if enable_thinking else "off"

        self.assertEqual(qs_mod._thinking_form(DirectOnly(), []), "direct")
        self.assertEqual(
            qs_mod._render_tokens(DirectOnly(), [], True, "direct"), 2)

        class Ignora:
            def apply_chat_template(self, messages, **kw):
                return "mismo"

        with self.assertRaises(SystemExit):
            qs_mod._thinking_form(Ignora(), [])

    def test_thinking_form_nested_preferida(self):
        self.assertEqual(qs_mod._thinking_form(_TokNested(), []), "nested")
        self.assertEqual(qs_mod._render_tokens(_TokNested(), [], True), 3)
        self.assertEqual(qs_mod._render_tokens(_TokNested(), [], False), 1)

    def test_render_tokens_extrae_input_ids_de_mapping(self):
        """D1-A / Enmienda 1: un tokenizer con el contrato de
        transformers 5.x (return_dict=True por defecto → dict/
        BatchEncoding aunque se pida return_dict=False) no cuenta
        CLAVES — se extrae input_ids cuando es inequívoco."""
        self.assertEqual(qs_mod._render_tokens(_TokBatchDict(), [], True),
                         5)
        self.assertEqual(qs_mod._render_tokens(_TokBatchDict(), [], False),
                         2)

    def test_render_tokens_rechaza_retornos_inesperados(self):
        """D1-A: str, bytes, batch anidado, mapping sin input_ids claro o
        secuencia vacía/no entera — todo retorno que no sea la secuencia
        plana de ids se rechaza, nunca se cuenta."""

        class TokStr:
            def apply_chat_template(self, messages, tokenize=True, **kw):
                return "texto renderizado"

        with self.assertRaises(SystemExit):
            qs_mod._render_tokens(TokStr(), [], False)

        class TokBatch:
            def apply_chat_template(self, messages, tokenize=True, **kw):
                return [[1, 2, 3], [4, 5]]

        with self.assertRaises(SystemExit):
            qs_mod._render_tokens(TokBatch(), [], False)

        class TokSinIds:
            def apply_chat_template(self, messages, tokenize=True, **kw):
                return {"attention_mask": [1, 1]}

        with self.assertRaises(SystemExit):
            qs_mod._render_tokens(TokSinIds(), [], False)

        class TokIdsAnidados:
            def apply_chat_template(self, messages, tokenize=True, **kw):
                return {"input_ids": [[1, 2, 3]]}

        with self.assertRaises(SystemExit):
            qs_mod._render_tokens(TokIdsAnidados(), [], False)

        class TokVacio:
            def apply_chat_template(self, messages, tokenize=True, **kw):
                return []

        with self.assertRaises(SystemExit):
            qs_mod._render_tokens(TokVacio(), [], False)

    def test_load_refs_rechaza_combo_ajeno(self):
        """El meta del fichero se verifica: referencias de otro combo no se
        cargan en silencio."""
        p = qs_mod._refs_path("prob_typesafe_on_d0")
        p.write_text(json.dumps(
            {"meta": {"combo": "prob_typesafe_on_d1"},
             "tokens": {"triage_es": {"T01": 7}}}))
        with self.assertRaises(SystemExit):
            qs_mod.load_refs("prob_typesafe_on_d0")
        p.write_text(json.dumps(
            {"meta": {"combo": "prob_typesafe_on_d0"},
             "tokens": {"triage_es": {"T01": 7}}}))
        self.assertEqual(qs_mod.load_refs("prob_typesafe_on_d0"),
                         {"triage_es": {"T01": 7}})


@unittest.skipUnless(HAS_LIB, "necesita system-one-adapter (.venv-llm)")
class TestBuildRefsIntegration(TmpStore):
    def test_build_refs_against_sink(self):
        """R16 §1: build_refs captura la request wire real del adaptador
        contra el sink local ({"body": {...}}); antes leía
        requests[-1]['body'] sobre el body plano → KeyError y bloqueaba las
        referencias de thinking/variantes."""
        with mock.patch.object(qs_mod, "PHASES_ALL", ["triage_es"]), \
             mock.patch.object(
                 qs_mod, "load_phase",
                 side_effect=lambda ph: (load_phase(ph)[0],
                                         load_phase(ph)[1][:1])):
            doc = qs_mod.build_refs("prob_typesafe_on_d0", _TokNested(),
                                    printer=lambda *a: None)
        self.assertEqual(doc["tokens"]["triage_es"],
                         {"T01_ebus_alergia": 3})
        self.assertEqual(doc["meta"]["render_kwarg"], "nested")
        self.assertEqual(doc["meta"]["combo"], "prob_typesafe_on_d0")
        self.assertEqual(doc["meta"]["chat_template_sha256"],
                         hashlib.sha256("tpl-stub".encode())
                         .hexdigest()[:12])
        # y el fichero queda verificable por load_refs
        self.assertEqual(qs_mod.load_refs("prob_typesafe_on_d0")
                         ["triage_es"]["T01_ebus_alergia"], 3)

    def test_build_refs_con_mapping_5x(self):
        """D1-A / Enmienda 1: con un tokenizer de contrato 5.x (mapping
        aunque se pida return_dict=False) build_refs cuenta los tokens de
        input_ids — nunca las 2 claves del mapping."""
        with mock.patch.object(qs_mod, "PHASES_ALL", ["triage_es"]), \
             mock.patch.object(
                 qs_mod, "load_phase",
                 side_effect=lambda ph: (load_phase(ph)[0],
                                         load_phase(ph)[1][:1])):
            doc = qs_mod.build_refs("prob_typesafe_on_d0", _TokBatchDict(),
                                    printer=lambda *a: None)
        self.assertEqual(doc["tokens"]["triage_es"],
                         {"T01_ebus_alergia": 5})
        self.assertEqual(doc["meta"]["render_kwarg"], "nested")


# Checkpoint real de Qwen3.8-27B (tokenizer) y el venv con transformers
# 5.x del diagnóstico D1 — el test se salta si no están en la máquina.
_TOK_DIR = Path("/tmp/jev70/qwen_tok")
_VENV_REFS_PY = Path("/tmp/jev70/venv-refs/bin/python")

_TOK_PROBE = r'''
import json, sys
sys.path.insert(0, {repo!r})
from pathlib import Path
from transformers import AutoTokenizer
from jevbench import qwen_session as q
tok = AutoTokenizer.from_pretrained({tok!r}, local_files_only=True)
arch = sorted(Path("results").glob("gate_qwen_prob_typesafe_on_d0~*"))[-1]
out = {{}}
for ph in ("adv1", "papers32", "ood"):
    gd = json.loads((arch / (ph + ".json")).read_text())
    cid, rec = next(iter(gd["cases"].items()))
    att = q.j67._first_attempt(rec)
    msgs = att["request"]["messages"]
    form = q._thinking_form(tok, msgs)
    got = q._render_tokens(tok, msgs, True, form)
    out[ph] = {{"case": cid, "got": got,
               "want": q.j67._first_prompt_tokens(rec)}}
print(json.dumps(out))
'''


@unittest.skipUnless(_TOK_DIR.is_dir() and _VENV_REFS_PY.exists(),
                     "checkpoint qwen_tok o venv-refs de D1 no presentes")
class TestRefsTokenizerReal(TmpStore):
    """Enmienda 1-A con el tokenizer real (transformers 5.x): el conteo
    de _render_tokens sobre los mensajes raw archivados de la puerta
    prob_typesafe_on_d0 coincide con usage.prompt_tokens del primer
    intento (D1: A01=842, P01=1982, receta=705). La sonda corre en el
    intérprete de venv-refs (transformers 5.x real); offline."""

    def test_render_tokens_contra_usage_archivado(self):
        repo = str(Path(qs_mod.__file__).resolve().parent.parent)
        gates = sorted(Path(repo, "results").glob("gate_qwen_prob_typesafe_on_d0~*"))
        if not gates or "raw" not in next(iter(json.loads(
                (gates[-1] / "adv1.json").read_text())["cases"].values())):
            # el espejo público sustituye raw por raw_sha256
            self.skipTest("mensajes raw de la puerta no archivados (export público)")
        # siempre el intérprete de venv-refs: es la transformers 5.x real
        # cuyo contrato causó el defecto, y evita los stubs que el propio
        # repo inyecta en sys.modules durante la suite (dgemma_gate)
        script = _TOK_PROBE.format(repo=repo, tok=str(_TOK_DIR))
        r = subprocess.run([str(_VENV_REFS_PY), "-c", script],
                           capture_output=True, text=True, cwd=repo,
                           timeout=300)
        self.assertEqual(r.returncode, 0, r.stderr[-2000:])
        res = json.loads(r.stdout.strip().splitlines()[-1])
        for ph, want in (("adv1", 842), ("papers32", 1982),
                         ("ood", 705)):
            self.assertEqual(res[ph]["got"], want, ph)
            self.assertEqual(res[ph]["want"], want, ph)


# ------------------------------------------------------------------ puerta

class _StubModel:
    """Adaptador mínimo para puerta/runner sin servidor ni librería. Emite
    un raw con la request real que haría el adaptador (esquema incrustado
    decodificable, thinking declarado, usage) para que la vigilancia por
    caso pueda acreditarla de verdad."""

    def __init__(self, payload=None, usage=10, meta=None, orders=None,
                 thinking=False, mode="probabilities", inject=True):
        self.payload = payload if payload is not None else ANSWERS
        self.usage = usage
        self._meta = meta or {"provider": "fake", "model": "m"}
        self.orders = orders
        self.thinking = thinking
        self.mode = mode
        self.inject = inject
        self.calls = 0

    def meta(self):
        return dict(self._meta)

    def _qs_eff(self, questions):
        return (reorder_choice(questions, self.orders)
                if self.orders else questions)

    def expected_system_prompt_sha256(self, questions):
        return _sha_of(_mk_request(self._qs_eff(questions), mode=self.mode,
                                   inject=self.inject,
                                   thinking=self.thinking))

    def decide(self, state, questions):
        self.calls += 1
        answers = (self.payload(state, questions) if callable(self.payload)
                   else self.payload)
        req = _mk_request(self._qs_eff(questions), mode=self.mode,
                          inject=self.inject, thinking=self.thinking,
                          state=state)
        resp = {"choices": [{"finish_reason": "stop",
                             "message": {"content": json.dumps(
                                 {"answers": answers})}}],
                "usage": {"prompt_tokens": self.usage}}
        if self.thinking:
            resp["choices"][0]["message"]["reasoning_content"] = "razonando"
        return {"answers": answers, "cost": None, "model": "m",
                "usage": {"input_tokens": self.usage, "attempts": 1},
                "raw": [{"request": req, "llm_response": resp}]}


def _mk_request(qs, order=None, inject=True, thinking=False, seed=101,
                mode="probabilities", state=None):
    """Request sintético del adaptador: system prompt con apéndice de
    esquema (decodificable), response_format, chat_template_kwargs y el
    payload <document> del usuario con el estado serializado (con
    `state`; sin ella, el contenido fijo "doc")."""
    schema = {"type": "object",
              "properties": {"answers": {"type": "object",
                                         "properties": {}}},
              "$defs": {}}
    props = {}
    for qid, q in qs.items():
        if q["type"] == "choice":
            crit = q["criteria"]
            labels = (order or {}).get(qid) or list(crit)
            if mode == "discrete":
                props[qid] = {
                    "description": q["instructions"] +
                    "\nChoice labels, answer with one label:\n" +
                    "\n".join(f"{l} = {crit[l]}" for l in labels),
                    "enum": labels, "type": "string"}
            else:
                props[qid] = {"description": q["instructions"],
                              "properties": {l: {"description": crit[l]}
                                             for l in labels},
                              "type": "object"}
        elif q["type"] == "score":
            if mode == "discrete":
                props[qid] = {
                    "description": q["instructions"] +
                    "\nScore levels:\n" +
                    "\n".join(f"{i} = {c}" for i, c in
                              enumerate(q["criteria"])),
                    "type": "integer"}
            else:
                props[qid] = {"description": q["instructions"],
                              "properties": {str(i): {"description": c}
                                             for i, c in
                                             enumerate(q["criteria"])},
                              "type": "object"}
        else:
            props[qid] = {"description": q["instructions"],
                          "type": "boolean" if mode == "discrete"
                          else "number"}
    schema["properties"]["answers"]["properties"] = props
    sysm = "base prompt"
    if inject:
        sysm += ("\n\n" + qs_mod.j67.SCHEMA_MARKER + json.dumps(schema)
                 + "\n\n" + qs_mod.j67.SCHEMA_TAIL)
    user = ("doc" if state is None
            else "<document>\n"
            + json.dumps(state, ensure_ascii=False)
            + "\n</document>")
    req = {"messages": [{"role": "system", "content": sysm},
                        {"role": "user", "content": user}],
           "response_format": {"json_schema": {"schema": schema}},
           "temperature": 0, "seed": seed}
    # thinking=None = combos sin flag (familia Gemma en jev77): la
    # petición no declara enable_thinking en absoluto
    if thinking is not None:
        req["chat_template_kwargs"] = {"enable_thinking": thinking}
    return req


def _mk_rec(request, answers=None, usage=10, reasoning=None):
    resp = {"choices": [{"finish_reason": "stop",
                         "message": {"role": "assistant",
                                     "content": json.dumps(
                                         {"answers": answers or {}})}}]}
    if usage is not None:
        resp["usage"] = {"prompt_tokens": usage}
    if reasoning is not None:
        resp["choices"][0]["message"]["reasoning_content"] = reasoning
    return {"answers": answers or {}, "raw": [{"request": request,
                                             "llm_response": resp}],
            "usage": {"input_tokens": usage}}


def _sha_of(req):
    return hashlib.sha256(
        req["messages"][0]["content"].encode()).hexdigest()[:12]


class TestGateChecks(TmpStore):
    def setUp(self):
        super().setUp()
        self.combo = {"mode": "probabilities", "prompt": "typesafe",
                      "thinking": False, "order": "d0"}
        self.qs = TRIAGE_QS

    def _fails(self, rec, exp_sha=None, hist=None, ref_on=None):
        if exp_sha is None and isinstance(rec, dict) and rec.get("raw"):
            exp_sha = _sha_of(rec["raw"][0]["request"])
        return qs_mod._gate_case_fails(
            self.combo, "triage_es", "T01", rec, self.qs, exp_sha,
            hist if hist is not None else {"triage_es": {"T01": 10}},
            ref_on, {}, {})

    def test_visible_ok(self):
        req = _mk_request(self.qs)
        rec = _mk_rec(req, usage=10)
        self.assertEqual(self._fails(rec, exp_sha=_sha_of(req)), [])

    def test_sha_mismatch_fails(self):
        rec = _mk_rec(_mk_request(self.qs))
        fails = self._fails(rec, exp_sha="deadbeefcafe")
        self.assertTrue(any("sha system" in f for f in fails))

    def test_wrong_order_fails(self):
        self.combo["order"] = "d1"
        rec = _mk_rec(_mk_request(self.qs))   # orden canónico, no d1
        fails = self._fails(rec)
        self.assertTrue(any("orden department" in f for f in fails))

    def test_missing_usage_fails(self):
        rec = _mk_rec(_mk_request(self.qs), usage=None)
        fails = self._fails(rec)
        self.assertTrue(any("sin usage" in f for f in fails))

    def test_no_raw_fails(self):
        self.assertIn("sin raw", self._fails({"answers": {}})[0])

    def test_thinking_off_observed_on_fails(self):
        req = _mk_request(self.qs, thinking=False)
        rec = _mk_rec(req, reasoning="pienso…")
        fails = self._fails(rec)
        self.assertTrue(any("thinking no efectivo" in f for f in fails))

    def test_thinking_on_sin_evidencia_ni_refs_fails(self):
        self.combo["thinking"] = True
        req = _mk_request(self.qs, thinking=True)
        rec = _mk_rec(req, reasoning="ok")
        fails = self._fails(rec)
        self.assertTrue(any("sin ref de tokens" in f for f in fails))

    def test_thinking_on_con_refs_pasa(self):
        self.combo["thinking"] = True
        req = _mk_request(self.qs, thinking=True)
        rec = _mk_rec(req, usage=300, reasoning="razonando…")
        ref_on = {"triage_es": {"T01": 300}}
        fails = self._fails(rec, ref_on=ref_on)
        self.assertEqual(fails, [])

    def test_thinking_on_sin_evidencia_fails(self):
        self.combo["thinking"] = True
        req = _mk_request(self.qs, thinking=True)
        rec = _mk_rec(req, usage=300)        # sin reasoning_content
        fails = self._fails(rec, ref_on={"triage_es": {"T01": 300}})
        self.assertTrue(any("thinking no efectivo" in f for f in fails))

    def test_token_rule_tol(self):
        # d0: +-2; d1-d3: +-10 sobre la referencia histórica
        rec = _mk_rec(_mk_request(self.qs), usage=13)
        self.assertTrue(any("fuera de referencia" in f
                            for f in self._fails(rec)))
        rec = _mk_rec(_mk_request(self.qs), usage=12)
        self.assertEqual(self._fails(rec), [])
        self.combo["order"] = "d2"
        req2 = _mk_request(self.qs, order={
            "department": NAMED_ORDERS["department"]["d2"]})
        rec = _mk_rec(req2, usage=19)
        self.assertEqual(self._fails(rec), [])
        rec = _mk_rec(req2, usage=21)
        self.assertTrue(any("fuera de referencia" in f
                            for f in self._fails(rec)))

    def test_disc_offsets(self):
        self.combo["mode"] = "discrete"
        req = _mk_request(self.qs, mode="discrete")
        rec = _mk_rec(req, usage=240)
        offsets = {}
        fails = qs_mod._gate_case_fails(
            self.combo, "adv1", "A01", rec, self.qs, _sha_of(req),
            {"adv1": {"A01": 300}}, None, {}, offsets)
        self.assertEqual(fails, [])
        self.assertEqual(offsets[qs_mod.family("adv1")], -60)

    def test_blind_ok(self):
        req = _mk_request(self.qs, inject=False)
        rec = _mk_rec(req, usage=5)
        fails, t = qs_mod._blind_fails(self.combo, "adv1/A01", rec, self.qs)
        self.assertEqual(fails, [])
        self.assertEqual(t, 5)

    def test_blind_with_appendix_fails(self):
        rec = _mk_rec(_mk_request(self.qs, inject=True), usage=5)
        fails, _ = qs_mod._blind_fails(self.combo, "adv1/A01", rec, self.qs)
        self.assertTrue(any("apéndice" in f for f in fails))

    def test_blind_with_questions_fails(self):
        req = _mk_request(self.qs, inject=False)
        req["messages"][0]["content"] += " " + \
            self.qs["department"]["instructions"]
        rec = _mk_rec(req, usage=5)
        fails, _ = qs_mod._blind_fails(self.combo, "adv1/A01", rec, self.qs)
        self.assertTrue(any("instrucciones" in f for f in fails))

    def test_canary_observacion_prob(self):
        """Enmienda 1: el canario se informa como observación — separación
        y coincidencia medidas, evidencia por lado anotada — sin producir
        fallos de puerta."""
        req_v = _mk_request(qs_mod.CANARY_QS,
                            state=qs_mod.CANARY_STATE)
        req_b = _mk_request(qs_mod.CANARY_QS, inject=False,
                            state=qs_mod.CANARY_STATE)
        av = {qs_mod.CANARY_QID: {"ruta_admin": 0.1,
                                  qs_mod.CANARY_LABEL: 0.85,
                                  "ruta_clinica": 0.05}}
        ab = {qs_mod.CANARY_QID: {"ruta_admin": 0.0,
                                  qs_mod.CANARY_LABEL: 0.0,
                                  "ruta_clinica": 0.0}}
        obs = qs_mod._canary_observation(_mk_rec(req_v, av),
                                         _mk_rec(req_b, ab), self.combo)
        self.assertTrue(obs["ejecutado"])
        self.assertAlmostEqual(obs["separacion"], 0.85)
        self.assertFalse(obs["ciego_coincide"])
        self.assertTrue(obs["visible_min_ok"])
        self.assertEqual(obs["visible"]["problemas"], [])
        self.assertEqual(obs["ciego"]["problemas"], [])
        self.assertEqual(obs["visible"]["usage"], 10)
        # el ciego asigna casi lo mismo al canario: coincidencia anotada,
        # no fallo (la etiqueta se puede elegir sin leer la descripción)
        ab2 = {qs_mod.CANARY_QID: {"ruta_admin": 0.1,
                                   qs_mod.CANARY_LABEL: 0.8,
                                   "ruta_clinica": 0.1}}
        obs2 = qs_mod._canary_observation(_mk_rec(req_v, av),
                                          _mk_rec(req_b, ab2), self.combo)
        self.assertTrue(obs2["ciego_coincide"])
        self.assertAlmostEqual(obs2["separacion"], 0.05)
        # el visible por debajo de CANARY_MIN también queda anotado
        av_low = {qs_mod.CANARY_QID: {"ruta_admin": 0.5,
                                      qs_mod.CANARY_LABEL: 0.1,
                                      "ruta_clinica": 0.4}}
        obs3 = qs_mod._canary_observation(_mk_rec(req_v, av_low),
                                          _mk_rec(req_b, ab), self.combo)
        self.assertFalse(obs3["visible_min_ok"])

    def test_canary_observacion_discrete(self):
        """En discrete la observación registra la elección de cada lado y
        la coincidencia del ciego."""
        self.combo["mode"] = "discrete"
        req_v = _mk_request(qs_mod.CANARY_QS, mode="discrete",
                            state=qs_mod.CANARY_STATE)
        req_b = _mk_request(qs_mod.CANARY_QS, inject=False,
                            mode="discrete",
                            state=qs_mod.CANARY_STATE)
        av = {qs_mod.CANARY_QID: qs_mod.CANARY_LABEL}
        ab = {qs_mod.CANARY_QID: "ruta_admin"}
        obs = qs_mod._canary_observation(_mk_rec(req_v, av),
                                         _mk_rec(req_b, ab), self.combo)
        self.assertEqual(obs["eleccion"]["visible"], qs_mod.CANARY_LABEL)
        self.assertFalse(obs["ciego_coincide"])
        self.assertTrue(obs["visible_min_ok"])
        # el ciego elige el canario sin verlo: coincidencia registrada
        obs2 = qs_mod._canary_observation(
            _mk_rec(req_v, av),
            _mk_rec(req_b, {qs_mod.CANARY_QID: qs_mod.CANARY_LABEL}),
            self.combo)
        self.assertTrue(obs2["ciego_coincide"])

    def test_canary_observacion_anota_evidencia(self):
        """La falta de evidencia (raw/usage del primer intento, apéndice
        presente en el ciego, respuesta no parseable, petición no
        ejecutada) se anota en la observación — no tumban la puerta."""
        req_v = _mk_request(qs_mod.CANARY_QS,
                            state=qs_mod.CANARY_STATE)
        req_b = _mk_request(qs_mod.CANARY_QS, inject=False,
                            state=qs_mod.CANARY_STATE)
        av = {qs_mod.CANARY_QID: {"ruta_admin": 0.0,
                                  qs_mod.CANARY_LABEL: 1.0,
                                  "ruta_clinica": 0.0}}
        ab = {qs_mod.CANARY_QID: {"ruta_admin": 0.0,
                                  qs_mod.CANARY_LABEL: 0.0,
                                  "ruta_clinica": 0.0}}
        rec_v = _mk_rec(req_v, av)
        # ciego sin raw alguno
        obs = qs_mod._canary_observation(rec_v, {}, self.combo)
        self.assertFalse(obs["ciego"]["raw"])
        self.assertTrue(obs["ciego"]["problemas"])
        # ciego con raw pero sin usage
        obs = qs_mod._canary_observation(
            rec_v, _mk_rec(req_b, ab, usage=None), self.combo)
        self.assertTrue(any("usage" in p
                            for p in obs["ciego"]["problemas"]))
        # ciego cuyo prompt lleva el apéndice (no es ciego de verdad)
        obs = qs_mod._canary_observation(
            rec_v, _mk_rec(req_v, ab), self.combo)
        self.assertTrue(obs["ciego"]["problemas"])
        # ciego sin respuesta parseable
        obs = qs_mod._canary_observation(rec_v, {"error": "x"},
                                         self.combo)
        self.assertTrue(any("error" in p
                            for p in obs["ciego"]["problemas"]))
        # peticiones no ejecutadas por presupuesto: va a `notas`
        obs = qs_mod._canary_observation(
            None, None, self.combo,
            notas=["canario visible: tope duro de 5000 peticiones "
                   "alcanzado"])
        self.assertFalse(obs["ejecutado"])
        self.assertTrue(obs["notas"])
        self.assertIn("no ejecutado", qs_mod._canary_resumen(obs))


@unittest.skipUnless(HAS_LIB, "necesita system-one-adapter (.venv-llm)")
class TestGateIntegration(TmpStore):
    """gate() extremo a extremo con el adaptador real y un servidor falso
    cuyo prompt_tokens depende de si el esquema viaja en el prompt."""

    def _serve(self, plan):
        from tests.test_llm_adapter import FakeOpenAIServer
        self.server = FakeOpenAIServer(plan)
        self.server.__enter__()
        self.addCleanup(self.server.__exit__)

    def _factory(self):
        from jevbench.adapters.llm import LLM
        base = self.server.base_url
        return lambda opts: LLM(**{**opts, "base_url": base})

    def _answers_from_schema(self, body):
        sch = body["response_format"]["json_schema"]["schema"]
        ans = sch["properties"]["answers"]
        ans = sch["$defs"][ans["$ref"].split("/")[-1]]
        out = {}
        for qid, field in ans["properties"].items():
            ref = (sch["$defs"][field["$ref"].split("/")[-1]]
                   if "$ref" in field else field)
            if "enum" in ref:
                out[qid] = ref["enum"][0]
            elif ref.get("properties"):
                out[qid] = {k: 0.0 for k in ref["properties"]}
            elif ref.get("type") == "boolean":
                out[qid] = False
            else:
                out[qid] = 0
        return out

    def _completion(self, text, tokens, reasoning=None):
        from tests.test_llm_adapter import _chat_completion
        resp = _chat_completion(text)
        resp["usage"]["prompt_tokens"] = tokens
        if reasoning is not None:
            resp["choices"][0]["message"]["reasoning_content"] = reasoning
        return resp

    def _plan(self):
        def plan(n, body):
            sysm = body["messages"][0]["content"]
            injected = "matches this schema exactly" in sysm
            if "visibility canary" in sysm:
                answers = {qs_mod.CANARY_QID: {
                    "ruta_admin": 0.05, qs_mod.CANARY_LABEL: 0.9,
                    "ruta_clinica": 0.05}}
            else:
                answers = self._answers_from_schema(body)
            return {"json": self._completion(
                json.dumps({"answers": answers}), 310 if injected else 10)}
        return plan

    def _hist(self):
        return {ph: {qs_mod.j67._gate_cases()[i][1].id: 310}
                for i, ph in enumerate(qs_mod.GATE_PHASES)}

    def test_gate_passes(self):
        self._serve(self._plan())
        ok, det = qs_mod.gate("prob_typesafe_off_d0", session="s1",
                              model_factory=self._factory(),
                              hist_ref=self._hist(), printer=lambda *a: None)
        self.assertTrue(ok, det["fails"])
        self.assertIn("gate_id", det)
        # el canario se ejecuta y se informa como observación (Enmienda 1)
        self.assertTrue(det["canary"]["ejecutado"])
        self.assertFalse(det["canary"]["ciego_coincide"])
        latest = qs_mod._latest_gate("prob_typesafe_off_d0")
        self.assertTrue(latest["ok"])
        self.assertEqual(latest["session"], "s1")
        self.assertEqual(latest["canary"]["rol"],
                         "observacion_enmienda1")

    def test_gate_canario_coincidente_pasa(self):
        """Enmienda 1: el ciego responde al canario igual que el visible —
        la observación registra la coincidencia y la puerta PASA igual
        (con el diseño anterior era FAIL)."""

        def plan(n, body):
            sysm = body["messages"][0]["content"]
            injected = "matches this schema exactly" in sysm
            # la descripción del canario viaja en el schema (presente en
            # ambas peticiones): el servidor la «obedece» también en el
            # ciego — una coincidencia no prueba visibilidad (D1-B)
            if "visibility canary" in json.dumps(body["response_format"]):
                answers = {qs_mod.CANARY_QID: {
                    "ruta_admin": 0.05, qs_mod.CANARY_LABEL: 0.9,
                    "ruta_clinica": 0.05}}
            else:
                answers = self._answers_from_schema(body)
            return {"json": self._completion(
                json.dumps({"answers": answers}), 310 if injected else 10)}

        self._serve(plan)
        ok, det = qs_mod.gate("prob_typesafe_off_d0", session="s1",
                              model_factory=self._factory(),
                              hist_ref=self._hist(), printer=lambda *a: None)
        self.assertTrue(ok, det["fails"])
        self.assertTrue(det["canary"]["ejecutado"])
        self.assertTrue(det["canary"]["ciego_coincide"])
        latest = qs_mod._latest_gate("prob_typesafe_off_d0")
        self.assertTrue(latest["canary"]["ciego_coincide"])

    def test_gate_fails_when_blind_not_blind(self):
        """El servidor inyecta por su cuenta: los tokens del ciego se acercan
        a los del visible (<200) y la puerta falla."""

        def plan(n, body):
            answers = self._answers_from_schema(body)
            return {"json": self._completion(
                json.dumps({"answers": answers}), 300)}
        self._serve(plan)
        ok, det = qs_mod.gate("prob_typesafe_off_d0", session="s1",
                              model_factory=self._factory(),
                              hist_ref=self._hist(), printer=lambda *a: None)
        self.assertFalse(ok)
        self.assertTrue(any("control negativo" in f for f in det["fails"]))

    def test_gate_fails_missing_ref_for_thinking(self):
        """Un combo `on` sin referencias precalculadas no verifica y falla."""
        self._serve(self._plan())
        ok, det = qs_mod.gate("prob_typesafe_on_d0", session="s1",
                              model_factory=self._factory(),
                              hist_ref=self._hist(), printer=lambda *a: None)
        self.assertFalse(ok)
        self.assertTrue(any("sin ref de tokens" in f or "thinking" in f
                            for f in det["fails"]))


# --------------------------------------------------------------- runner

def _fake_cell(run="t_run", **kw):
    cell = {"run": run, "issue": "JEV-68", "mode": "probabilities",
            "thinking": False, "order": "d0", "seed": 101,
            "phases": ["triage_es"], "budget_s": 600}
    cell.update(kw)
    return cell


def _default_hist():
    return {"triage_es": {c.id: 10 for c in load_phase("triage_es")[1]}}


def _ctx(cells, model=None, st=None, hist=None):
    st = st or {"session": "s1", "started": "x", "elapsed_s": 0.0,
                "requests": 0, "cell_s": {}, "retried": {},
                "sessions": ["s1"]}
    m = model or _StubModel()
    models = {k: m for k in cells}
    # el sha esperado se precomputa por celda×fase, como en _build_ctx
    exp_sha = {}
    for name, c in cells.items():
        for ph in c["phases"]:
            qs_, _ = load_phase(ph)
            exp_sha[(name, ph)] = models[name].expected_system_prompt_sha256(qs_)
    return {"st": st, "hist": hist if hist is not None else _default_hist(),
            "refs_on": {}, "offsets": {}, "models": models,
            "exp_sha": exp_sha, "gate_ids": {}, "gate_entries": {},
            "cell_stop": {}, "session_stop": None,
            "no_usage": {}, "cells": cells, "t0": 0.0,
            "elapsed_base": st.get("elapsed_s", 0.0), "manifest": None}


class TestExecSlot(TmpStore):
    def _slot(self, cell_name="T", cell=None, retry=False, **ctxkw):
        cell = cell or _fake_cell()
        cells = {cell_name: cell}
        ctx = _ctx(cells, **ctxkw)
        out = []
        printer = lambda *a, **k: out.append(" ".join(str(x) for x in a))
        qs_mod._exec_slot(ctx, cell_name, "triage_es", retry,
                          mock.Mock(return_value=0.0), lambda s: None,
                          printer)
        return ctx, out

    def test_completes_and_writes(self):
        ctx, out = self._slot()
        doc = store.load("t_run", "triage_es")
        self.assertEqual(len(doc["cases"]), 14)
        self.assertIn("raw", doc["cases"]["T01_ebus_alergia"])
        self.assertEqual(doc["meta"]["diag"]["rotation"]["order"]
                         ["department"], NAMED_ORDERS["department"]["d0"])

    def test_token_violation_stops_cell(self):
        hist = {"triage_es": {c.id: 900
                              for c in load_phase("triage_es")[1]}}
        ctx, out = self._slot(hist=hist)
        self.assertIn("T", ctx["cell_stop"])
        self.assertIn("visibilidad", ctx["cell_stop"]["T"])
        doc = store.load("t_run", "triage_es")
        self.assertEqual(len(doc["cases"]), 1)

    def test_missing_ref_is_violation(self):
        ctx, out = self._slot(hist={"triage_es": {}})
        self.assertIn("sin ref", ctx["cell_stop"]["T"])

    def test_three_errors_stop_phase(self):
        class M(_StubModel):
            def decide(self, s, q):
                self.calls += 1
                if self.calls <= 3:
                    raise RuntimeError("boom")
                return super().decide(s, q)
        ctx, out = self._slot(model=M())
        doc = store.load("t_run", "triage_es")
        errs = sum(1 for r in doc["cases"].values() if "error" in r)
        self.assertEqual(errs, 3)
        self.assertEqual(len(doc["cases"]), 3)
        self.assertEqual(len(doc["meta"]["diag"]["stopped_cases"]), 11)

    def test_request_cap_stops_session(self):
        st = {"session": "s1", "started": "x", "elapsed_s": 0.0,
              "requests": qs_mod.REQUEST_CAP, "cell_s": {}, "retried": {},
              "sessions": ["s1"]}
        ctx, out = self._slot(st=st)
        self.assertEqual(ctx["session_stop"],
                         f"tope duro de {qs_mod.REQUEST_CAP} peticiones")
        doc = store.load("t_run", "triage_es")
        self.assertEqual(len(doc["cases"]), 0)

    def test_cell_budget_stops_cell(self):
        cell = _fake_cell(budget_s=10)
        st = {"session": "s1", "started": "x", "elapsed_s": 0.0,
              "requests": 0, "cell_s": {"T": 20.0}, "retried": {},
              "sessions": ["s1"]}
        ctx, out = self._slot(cell=cell, st=st)
        self.assertIn("presupuesto de celda", ctx["cell_stop"]["T"])

    def test_resume_rejects_different_config(self):
        ctx, out = self._slot()
        cells = {"T": _fake_cell(seed=202)}
        ctx2 = _ctx(cells)
        ctx2["st"] = ctx["st"]
        with self.assertRaises(SystemExit):
            qs_mod._validate_existing(ctx2, cells, ["T"], lambda *a: None)

    def test_retry_errors_only_once(self):
        class M(_StubModel):
            def decide(self, s, q):
                self.calls += 1
                if self.calls <= 2:
                    raise RuntimeError("boom")
                return super().decide(s, q)
        ctx, out = self._slot(model=M())
        doc = store.load("t_run", "triage_es")
        self.assertEqual(sum(1 for r in doc["cases"].values()
                             if "error" in r), 2)
        qs_mod._exec_slot(ctx, "T", "triage_es", True,
                          mock.Mock(return_value=0.0), lambda s: None,
                          lambda *a, **k: None)
        doc = store.load("t_run", "triage_es")
        self.assertEqual(sum(1 for r in doc["cases"].values()
                             if "error" in r), 0)
        self.assertEqual(len(ctx["st"]["retried"]["t_run/triage_es"]), 2)

    def test_case_without_raw_stops_cell(self):
        """R16 §3: la regla ya no corre 'solo si existe raw' — un caso sin
        captura no acredita visibilidad y detiene la celda."""
        class NoRaw(_StubModel):
            def decide(self, *a, **k):
                out = super().decide(*a, **k)
                out.pop("raw")
                return out
        ctx, out = self._slot(cell=_fake_cell(run="noraw"),
                              model=NoRaw())
        self.assertIn("visibilidad no acreditada", ctx["cell_stop"]["T"])
        doc = store.load("noraw", "triage_es")
        self.assertEqual(len(doc["cases"]), 1)

    def test_client_checked_even_when_tokens_match(self):
        """R16 §3: tokens dentro de referencia no bastan — el prompt, el
        esquema y el thinking declarado se verifican en CADA caso."""
        # el stub emite un request sin apéndice (inject=False): los tokens
        # coinciden con la referencia pero el cliente no es el declarado
        ctx, out = self._slot(cell=_fake_cell(run="wrongclient"),
                              model=_StubModel(inject=False))
        self.assertIn("visibilidad no acreditada", ctx["cell_stop"]["T"])
        doc = store.load("wrongclient", "triage_es")
        self.assertEqual(len(doc["cases"]), 1)

    def test_request_cap_reserves_attempts(self):
        """R16 §6: el tope de 5000 es duro por petición — con 4999
        acumuladas un caso que puede consumir 3 intentos no se abre (se
        reserva el máximo antes de la petición)."""
        model = _StubModel()
        st = {"session": "s1", "started": "x", "elapsed_s": 0.0,
              "requests": qs_mod.REQUEST_CAP - 1, "cell_s": {},
              "retried": {}, "sessions": ["s1"]}
        ctx, out = self._slot(cell=_fake_cell(run="cap"), model=model,
                              st=st)
        self.assertEqual(model.calls, 0)
        self.assertEqual(ctx["session_stop"],
                         f"tope duro de {qs_mod.REQUEST_CAP} peticiones")
        self.assertLessEqual(st["requests"], qs_mod.REQUEST_CAP)

    def test_attempts_counts_transport_retries(self):
        """R16 §6: diag.attempts registra cada llamada HTTP real, incluidos
        los fallos de transporte que nunca devolvieron usage."""
        self.assertEqual(qs_mod._attempts(
            {"error": "x", "diag": {"attempts": 3}}), 3)
        self.assertEqual(qs_mod._attempts({"error": "x"}), 1)
        self.assertEqual(qs_mod._attempts(
            {"usage": {"attempts": 2}, "raw": [1, 1]}), 2)

    def test_run_errors_precheck(self):
        """R16 §6: un run que ya acumuló 10 errores no abre ni una petición
        más — la regla se comprueba antes del caso, no después."""
        model = _StubModel()
        cells = {"T": _fake_cell(run="err10")}
        ctx = _ctx(cells, model=model)
        store.save("err10", "adv3",
                   {"meta": {}, "cases": {f"c{i}": {"error": "boom"}
                                          for i in range(10)}})
        qs_mod._exec_slot(ctx, "T", "triage_es", False,
                          mock.Mock(return_value=0.0), lambda s: None,
                          lambda *a, **k: None)
        self.assertEqual(model.calls, 0)
        self.assertIn("10 errores", ctx["cell_stop"]["T"])
        self.assertEqual(store.load("err10", "triage_es")["cases"], {})


class TestRunEndToEnd(TmpStore):
    def _patch_env(self):
        cells = {"T": _fake_cell()}
        key = qs_mod.cell_gate_key(cells["T"])
        _write_gate_archive(key, "g@t", hist=_default_hist())
        patches = [
            mock.patch.object(qs_mod, "CELLS", cells),
            mock.patch.object(qs_mod, "_calendar",
                              lambda: [("T", "triage_es")]),
            mock.patch.object(qs_mod.j67, "load_token_ref",
                              _default_hist),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        # el ejecutor exige el manifiesto congelado por el dry-run (R17 §6)
        qs_mod._manifest_path().write_text(
            json.dumps(qs_mod._plan_manifest(), ensure_ascii=False))
        return cells, key

    def test_run_completes(self):
        cells, key = self._patch_env()
        rc = qs_mod.run(session="s1",
                        model_factory=lambda o: _StubModel(),
                        now=mock.Mock(return_value=0.0),
                        printer=lambda *a: None)
        self.assertEqual(rc, 0)
        doc = store.load("t_run", "triage_es")
        self.assertEqual(len(doc["cases"]), 14)
        self.assertEqual(doc["meta"]["diag"]["status"], "complete")
        st = qs_mod._load_state()
        self.assertEqual(st["requests"], 14)

    def test_run_without_gate_stops(self):
        cells = {"T": _fake_cell()}
        with mock.patch.object(qs_mod, "CELLS", cells), \
             mock.patch.object(qs_mod, "_calendar",
                               lambda: [("T", "triage_es")]), \
             mock.patch.object(qs_mod.j67, "load_token_ref",
                               _default_hist):
            qs_mod._manifest_path().write_text(
                json.dumps(qs_mod._plan_manifest(), ensure_ascii=False))
            rc = qs_mod.run(session="s1",
                            model_factory=lambda o: _StubModel(),
                            now=mock.Mock(return_value=0.0),
                            printer=lambda *a: None)
        self.assertEqual(rc, 2)
        self.assertIsNone(store.load("t_run", "triage_es"))

    def test_run_existing_without_resume_rejects(self):
        cells, key = self._patch_env()
        store.save("t_run", "triage_es", {"meta": {}, "cases": {}})
        rc = qs_mod.run(session="s1",
                        model_factory=lambda o: _StubModel(),
                        now=mock.Mock(return_value=0.0),
                        printer=lambda *a: None)
        self.assertEqual(rc, 1)

    def test_run_session_mismatch_rejects(self):
        qs_mod.session_begin("otra")
        with self.assertRaises(SystemExit):
            qs_mod.run(session="s1",
                       model_factory=lambda o: _StubModel(),
                       printer=lambda *a: None)


class TestCalendar(TmpStore):   # plan() exporta el manifiesto a logs/
    def test_calendar_frozen(self):
        slots = qs_mod._calendar()
        base = qs_mod.CALENDAR_BASE
        for i, ph in enumerate(qs_mod.PHASES_ALL):
            want = base[i % len(base):] + base[:i % len(base)]
            chunk = [c for c, p in slots if p == ph]
            exp = list(want) + (["S202"] if ph in ("papers32", "adv3") else [])
            self.assertEqual(chunk, exp, ph)
        self.assertEqual(len(slots), 11 * 7 + 2)

    def test_cell_table(self):
        self.assertEqual(qs_mod.CELLS["F0"]["run"],
                         "llm_qwen38_27b_fp8_jev68_off_d0_prob")
        self.assertEqual(qs_mod.CELLS["D0"]["mode"], "discrete")
        self.assertTrue(qs_mod.CELLS["T0"]["thinking"])
        self.assertEqual(qs_mod.CELLS["S202"]["phases"],
                         ["papers32", "adv3"])
        for name, cell in qs_mod.CELLS.items():
            self.assertIn(cell["order"], NAMED_ORDERS["department"])

    def test_gate_keys(self):
        self.assertEqual(qs_mod.cell_gate_key(qs_mod.CELLS["T1"]),
                         "prob_typesafe_on_d1")
        self.assertEqual(qs_mod.cell_gate_key(qs_mod.CELLS["D0"]),
                         "disc_typesafe_off_d0")
        combos = qs_mod.combos_needed()
        self.assertIn("prob_sin_antinj_off_d0", combos)
        self.assertIn("prob_antinj_alt_off_d0", combos)

    def test_parse_gate_key(self):
        c = qs_mod.parse_gate_key("disc_sin_antinj_on_d2")
        self.assertEqual(c["mode"], "discrete")
        self.assertTrue(c["thinking"])
        self.assertEqual(c["order"], "d2")
        with self.assertRaises(SystemExit):
            qs_mod.parse_gate_key("prob_typesafe_off_d4")

    def test_p712_manifesto_p03(self):
        """R16 §2 + decisión del operador (6-oct-2026): P03 sustituye a P02
        — mismo state en GT v3, diseño intacto — y el manifiesto resuelve
        contra la batería sin abortar."""
        self.assertIn(("papers32", "P03"), qs_mod.P712_CASES)
        self.assertNotIn(("papers32", "P02"), qs_mod.P712_CASES)
        pcs = qs_mod.p712_cases()
        self.assertEqual(len(pcs), 12)
        self.assertTrue(any(c.id == "P03" for _, c in pcs))

    def test_dry_run_prints_gates_and_slots(self):
        out = []
        qs_mod.plan(out.append)
        text = "\n".join(out)
        for key in qs_mod.combos_needed():
            self.assertIn(f"gate {key}", text)
        self.assertIn("slot", text)
        self.assertIn("5000", text)
        self.assertIn("qwen_session diag", text)

    def test_dry_run_manifiesto_exacto(self):
        """R16 §10: el dry-run congela exactamente lo ejecutable — sha del
        manifiesto, opciones efectivas completas por celda (thinking/seed/
        orden/modo), orden de fases e ids exactos de los diagnósticos."""
        out = []
        qs_mod.plan(out.append)
        text = "\n".join(out)
        self.assertIn("manifest_sha256=", text)
        # la enmienda P03 aparece en el plan (y P02 ya no)
        self.assertIn("'papers32', 'P03'", text)
        self.assertNotIn("P02", text)
        # opciones efectivas por celda, no solo las de F0 (extra_body va
        # como cadena JSON dentro de opts, con comillas escapadas)
        self.assertIn('enable_thinking\\": true', text)
        self.assertIn('enable_thinking\\": false', text)
        self.assertIn('seed\\": 202', text)
        self.assertIn('"choice_order": "department:d3"', text)
        # orden real de fases y los 12 ids exactos de los diagnósticos
        self.assertIn("['adv1', 'adv3', 'ood', 'papers32', 'triage_es', "
                      "'triage_ext_en']", text)
        for _, cid in qs_mod.P712_CASES:
            self.assertIn(cid, text)
        # el sha del manifiesto es determinista entre llamadas
        self.assertEqual(qs_mod._plan_manifest()["manifest_sha256"],
                         qs_mod._plan_manifest()["manifest_sha256"])
        # y el ejecutor consume lo que el plan anuncia
        man = qs_mod._plan_manifest()
        self.assertEqual([tuple(pc) for pc in man["p712_cases"]],
                         qs_mod.P712_CASES)
        self.assertEqual(len(man["slots"]), 79)
        self.assertEqual(len(man["diag"]), 9)


# ---------------------------------------------------------------- sesión

class TestSession(TmpStore):
    def test_session_begin_and_mismatch(self):
        st = qs_mod.session_begin("s1")
        self.assertEqual(st["session"], "s1")
        self.assertEqual(qs_mod.session_begin("s1")["session"], "s1")
        with self.assertRaises(SystemExit):
            qs_mod.session_begin("otra")
        st = qs_mod.session_begin("s2", new_session=True)
        self.assertEqual(st["session"], "s2")
        self.assertIn("s1", st["sessions"])

    def test_gate_session_linkage(self):
        """latest_gate de otra sesión no habilita la celda."""
        cells = {"T": _fake_cell()}
        ctx = _ctx(cells)
        key = qs_mod.cell_gate_key(cells["T"])
        store.save(f"gate_qwen_{key}", "adv1",
                   {"meta": {"diag": {"latest_gate": {
                       "gate_id": "g@t", "ok": True, "session": "otra",
                       "ts": "a"}}}, "cases": {}})
        self.assertFalse(qs_mod._cell_gate_ok(ctx, cells["T"]))
        store.save(f"gate_qwen_{key}", "adv2",
                   {"meta": {"diag": {"latest_gate": {
                       "gate_id": "g@t2", "ok": True, "session": "s1",
                       "ts": "z",
                       "refs": _hist_refs(key, _default_hist())}}},
                    "cases": {}})
        ctx2 = _ctx(cells)
        self.assertTrue(qs_mod._cell_gate_ok(ctx2, cells["T"]))

    def test_lock_exclusive(self):
        fd = qs_mod._acquire_lock()
        try:
            with self.assertRaises(FileExistsError):
                qs_mod._acquire_lock()
        finally:
            qs_mod._release_lock(fd)

    def test_session_begin_requires_lock_ownership(self):
        """Una mutación de sesión no puede ocurrir mientras el lock lo
        tiene otro proceso (fichero presente, fd no nuestro)."""
        p = qs_mod._lock_path()
        p.write_text("99999 otro\n")
        try:
            with self.assertRaises(SystemExit):
                qs_mod.session_begin("s1")
        finally:
            p.unlink()

    def test_new_session_keeps_elapsed_budget(self):
        """R16 §6: el reinicio del servidor NO amplía el presupuesto del
        encargo — elapsed_s, peticiones y tiempos por celda se conservan;
        solo las puertas quedan ligadas al nuevo id."""
        st = qs_mod.session_begin("s1")
        st["elapsed_s"] = 35999.0
        st["requests"] = 123
        qs_mod._save_state(st)
        st = qs_mod.session_begin("s2", new_session=True)
        self.assertEqual(st["elapsed_s"], 35999.0)
        self.assertEqual(st["requests"], 123)
        self.assertIn("s1", st["sessions"])

    def test_contadores_no_se_reinician(self):
        """Enmienda 1 (qwen38_jev68 §14): las peticiones de las puertas
        descartadas cuentan — ni session_begin ni _save_state permiten
        reiniciar los acumulados (requests, elapsed_s, cell_s por celda
        ni el historial de sesiones)."""
        st = qs_mod.session_begin("s1")
        st["requests"] = 54
        st["elapsed_s"] = 100.0
        st["cell_s"]["X"] = 50.0
        qs_mod._save_state(st)
        st = qs_mod.session_begin("s2", new_session=True)
        self.assertEqual(st["requests"], 54)
        self.assertEqual(st["elapsed_s"], 100.0)
        self.assertEqual(st["cell_s"]["X"], 50.0)
        self.assertEqual(st["sessions"], ["s1", "s2"])
        # un guardado que retroceda cualquier acumulado se rechaza y el
        # fichero queda intacto
        for mut in ({"requests": 0}, {"elapsed_s": 1.0}, {"cell_s": {}},
                    {"cell_s": {"X": 10.0}}, {"sessions": ["s2"]}):
            mal = qs_mod._load_state()
            mal.update(mut)
            with self.assertRaises(SystemExit):
                qs_mod._save_state(mal)
        final = qs_mod._load_state()
        self.assertEqual(final["requests"], 54)
        self.assertEqual(final["elapsed_s"], 100.0)
        self.assertEqual(final["cell_s"]["X"], 50.0)
        self.assertEqual(final["sessions"], ["s1", "s2"])
        # un guardado igual o creciente sí pasa
        final["requests"] = 55
        qs_mod._save_state(final)
        self.assertEqual(qs_mod._load_state()["requests"], 55)

    def test_cases_keep_session_and_gate_provenance(self):
        """R16 §5: cada record lleva su sesión y el gate_id que lo
        autorizó; reanudar bajo otra sesión conserva la identidad de los
        casos antiguos (el meta declara las dos sesiones, no relabela)."""
        cells = {"T": _fake_cell(run="resume")}
        ctx = _ctx(cells)
        key = qs_mod.cell_gate_key(cells["T"])
        ctx["gate_ids"][key] = "gate_qwen_x@s1~u1"
        args = (False, mock.Mock(return_value=0.0), lambda s: None,
                lambda *a, **k: None)
        qs_mod._exec_slot(ctx, "T", "triage_es", *args)
        doc = store.load("resume", "triage_es")
        self.assertTrue(all(r.get("session") == "s1"
                            for r in doc["cases"].values()))
        self.assertTrue(all(r.get("gate_id") == "gate_qwen_x@s1~u1"
                            for r in doc["cases"].values()))
        # reanudación bajo otra sesión
        ctx["st"]["session"] = "s2"
        ctx["st"]["sessions"] = ["s1", "s2"]
        ctx["gate_ids"][key] = "gate_qwen_x@s2~u2"
        borrado = next(iter(doc["cases"]))
        del doc["cases"][borrado]
        store.save("resume", "triage_es", doc)
        qs_mod._exec_slot(ctx, "T", "triage_es", *args)
        doc = store.load("resume", "triage_es")
        self.assertEqual(doc["cases"][borrado]["session"], "s2")
        self.assertEqual(doc["cases"][borrado]["gate_id"],
                         "gate_qwen_x@s2~u2")
        self.assertIn("s1", doc["meta"]["diag"]["sessions"])
        self.assertIn("s2", doc["meta"]["diag"]["sessions"])
        otros = [r for c, r in doc["cases"].items() if c != borrado]
        self.assertTrue(all(r["session"] == "s1" for r in otros))
        self.assertTrue(all(r["gate_id"] == "gate_qwen_x@s1~u1"
                            for r in otros))


class TestGateEvidence(TmpStore):
    """R16 §5: la puerta corre bajo el mismo lock que run/diag y cada
    ejecución deja evidencia inmutable ligada a un gate_id único."""

    def _hist(self):
        return {ph: {case.id: 310} for ph, case in qs_mod._gate_cases()}

    def _factory(self, canary_v=0.9, canary_b=0.0):
        def factory(opts):
            inj = opts["inject_schema_in_prompt"] == "true"

            def payload(state, questions):
                if qs_mod.CANARY_QID in questions:
                    p = canary_v if inj else canary_b
                    return {qs_mod.CANARY_QID: {
                        "ruta_admin": 1 - p, qs_mod.CANARY_LABEL: p,
                        "ruta_clinica": 0.0}}
                return ANSWERS

            return _StubModel(payload=payload, usage=310 if inj else 10,
                              inject=inj)
        return factory

    def test_gate_requires_lock(self):
        fd = qs_mod._acquire_lock()
        try:
            with self.assertRaises(SystemExit):
                qs_mod.gate("prob_typesafe_off_d0", session="s1",
                            model_factory=self._factory(),
                            hist_ref=self._hist(), printer=lambda *a: None)
        finally:
            qs_mod._release_lock(fd)

    def test_gate_ids_unicos_y_evidencia_inmutable(self):
        key = "prob_typesafe_off_d0"
        ok1, d1 = qs_mod.gate(key, session="s1",
                              model_factory=self._factory(canary_v=0.9),
                              hist_ref=self._hist(), printer=lambda *a: None)
        self.assertTrue(ok1, d1["fails"])
        # la puerta descuenta sus peticiones del tope compartido
        st = qs_mod._load_state()
        self.assertGreaterEqual(st["requests"], 6)
        self.assertIn("elapsed_s", st)
        # una segunda ejecución de la MISMA puerta en la misma sesión no
        # reescribe la evidencia de la primera
        ok2, d2 = qs_mod.gate(key, session="s1",
                              model_factory=self._factory(canary_v=0.7),
                              hist_ref=self._hist(), printer=lambda *a: None)
        self.assertTrue(ok2, d2["fails"])
        self.assertNotEqual(d1["gate_id"], d2["gate_id"])
        uid1 = d1["gate_id"].rsplit("~", 1)[-1]
        uid2 = d2["gate_id"].rsplit("~", 1)[-1]
        c1 = store.load(f"gate_qwen_{key}~{uid1}", "canary")["cases"]
        c2 = store.load(f"gate_qwen_{key}~{uid2}", "canary")["cases"]
        self.assertEqual(c1["canary"]["answers"][qs_mod.CANARY_QID]
                         [qs_mod.CANARY_LABEL], 0.9)
        self.assertEqual(c2["canary"]["answers"][qs_mod.CANARY_QID]
                         [qs_mod.CANARY_LABEL], 0.7)
        latest = qs_mod._latest_gate(key)
        self.assertEqual(latest["gate_id"], d2["gate_id"])
        # la entrada de la primera sigue resoluble para la auditoría
        self.assertEqual(
            qs_mod._gate_entry_for(key, d1["gate_id"])["gate_id"],
            d1["gate_id"])
        # y sus offsets/tokens van en el propio entry
        self.assertIn("tokens", latest)

    def test_gate_canario_coincidente_stub_pasa(self):
        """Enmienda 1: canario coincidente ciego/visible → la puerta PASA
        y la observación queda registrada en el entry inmutable y en la
        salida (ciego_coincide)."""
        key = "prob_typesafe_off_d0"
        ok, det = qs_mod.gate(
            key, session="s1",
            model_factory=self._factory(canary_v=0.9, canary_b=0.9),
            hist_ref=self._hist(), printer=lambda *a: None)
        self.assertTrue(ok, det["fails"])
        obs = det["canary"]
        self.assertTrue(obs["ejecutado"])
        self.assertTrue(obs["ciego_coincide"])
        latest = qs_mod._latest_gate(key)
        self.assertTrue(latest["canary"]["ciego_coincide"])
        self.assertEqual(latest["canary"]["rol"],
                         "observacion_enmienda1")

    def test_gate_falla_control_ciego_por_tokens(self):
        """Lo que sigue BLOQUEANTE: visible−ciego < 200 tokens en A01 →
        FAIL, aunque el canario (observación) registre coincidencia."""

        def factory(opts):
            inj = opts["inject_schema_in_prompt"] == "true"

            def payload(state, questions):
                if qs_mod.CANARY_QID in questions:
                    return {qs_mod.CANARY_QID: {
                        "ruta_admin": 0.1, qs_mod.CANARY_LABEL: 0.9,
                        "ruta_clinica": 0.0}}
                return ANSWERS

            # el ciego casi iguala los tokens del visible: diferencia 20
            return _StubModel(payload=payload, usage=310 if inj else 290,
                              inject=inj)

        ok, det = qs_mod.gate("prob_typesafe_off_d0", session="s1",
                              model_factory=factory,
                              hist_ref=self._hist(), printer=lambda *a: None)
        self.assertFalse(ok)
        self.assertTrue(any("control negativo" in f
                            for f in det["fails"]))
        # el canario se ejecutó y su coincidencia quedó anotada, no
        # bloqueó ni salvó nada
        self.assertTrue(det["canary"]["ejecutado"])
        self.assertTrue(det["canary"]["ciego_coincide"])

    def test_gate_peticiones_se_acumulan(self):
        """Enmienda 1: las sondas de puerta descuentan del tope
        compartido sin reiniciarlo — cada puerta suma, nunca resetea."""
        key = "prob_typesafe_off_d0"
        qs_mod.gate(key, session="s1", model_factory=self._factory(),
                    hist_ref=self._hist(), printer=lambda *a: None)
        n1 = qs_mod._load_state()["requests"]
        self.assertGreater(n1, 0)
        qs_mod.gate(key, session="s1", model_factory=self._factory(),
                    hist_ref=self._hist(), printer=lambda *a: None)
        self.assertEqual(qs_mod._load_state()["requests"], n1 * 2)


# ---------------------------------------------------------------- análisis

def _answers_hit(qs, gt):
    out = {}
    for qid, q in qs.items():
        if q["type"] == "choice":
            out[qid] = {"choice": gt[qid],
                        "probabilities": {k: (1.0 if k == gt[qid] else 0.0)
                                          for k in q["criteria"]}}
        elif q["type"] == "score":
            out[qid] = {"score": float(gt[qid]),
                        "probabilities": {str(i): (1.0 if i == gt[qid]
                                                  else 0.0)
                                          for i in range(len(q["criteria"]))}}
        else:
            out[qid] = {"noul": float(gt[qid])}
    return out


def _answers_miss(qs, gt):
    out = {}
    for qid, q in qs.items():
        if q["type"] == "choice":
            bad = next(k for k in q["criteria"] if k != gt[qid])
            out[qid] = {"choice": bad,
                        "probabilities": {k: (1.0 if k == bad else 0.0)
                                          for k in q["criteria"]}}
        elif q["type"] == "score":
            bad = 2 if gt[qid] == 0 else 0
            out[qid] = {"score": float(bad),
                        "probabilities": {str(i): (1.0 if i == bad else 0.0)
                                          for i in range(len(q["criteria"]))}}
        else:
            out[qid] = {"noul": float(1 - gt[qid])}
    return out


def _hist_refs(key, hist):
    """La referencia histórica congelada en la evidencia de una puerta
    (formato post-C12): run de procedencia + doc completo verificado por
    doc_sha256 — misma forma que las referencias tokenizer."""
    hdoc = {"meta": {"ref_run": qs_mod.REF_RUN, "combo": key},
            "tokens": hist}
    return {"run": qs_mod.REF_RUN, "doc_sha256": qs_mod._doc_sha(hdoc),
            "doc": hdoc}


def _write_gate_archive(key, gate_id, ok=True, session="s1", refs_doc=None,
                        offsets=None, hist=None):
    """Evidencia inmutable mínima de una puerta: un doc del archivo
    gate_qwen_<key>~<uid> con la entrada del gate_id dado. `refs_doc`
    archiva la referencia de tokens completa que autorizó la puerta
    (formato post-C11: doc + doc_sha256); `hist` archiva la referencia
    histórica congelada de REF_RUN para los combos off/typesafe y
    discrete (post-C12); `offsets` fija los offsets de discrete medidos
    por la puerta."""
    entry = {"gate_id": gate_id, "ts": "t", "ok": ok, "session": session,
             "fails": []}
    if refs_doc is not None:
        entry["refs"] = {"file": f"qwen_refs_{key}.json",
                         "doc_sha256": qs_mod._doc_sha(refs_doc),
                         "doc": refs_doc}
    elif hist is not None:
        entry["refs"] = _hist_refs(key, hist)
    if offsets is not None:
        entry["offsets"] = dict(offsets)
    doc = {"meta": {"diag": {"gate_history": [entry],
                             "latest_gate": entry}}, "cases": {}}
    # como la puerta real: archivo inmutable ~uid + puntero latest (el
    # directorio es el del perfil vigente — gate_qwen_* en jev68)
    store.save(f"{qs_mod._gate_run(key)}~{gate_id.rsplit('~', 1)[-1]}",
               "adv1", doc)
    store.save(qs_mod._gate_run(key), "adv1", doc)


def _write_run(run, phase, hit=True, raw=False, session="s1", gate_id=None,
               usage=10, mode="probabilities", order=None, thinking=False,
               reasoning=None):
    """Escribe un run sintético. raw=True añade la evidencia que exige la
    vigilancia: request con esquema decodificable, usage y sha del system
    prompt en meta (más rec.session/rec.gate_id si se pasa gate_id)."""
    qs, cases = load_phase(phase)
    req = (_mk_request(qs, order=order, thinking=thinking, mode=mode)
           if raw else None)
    recs = {}
    for c in cases:
        a = _answers_hit(qs, c.gt) if hit else _answers_miss(qs, c.gt)
        if raw:
            # el estado del caso viaja en el payload <document>, como en
            # la request real del adaptador (la vigilancia lo exige)
            req_c = _mk_request(qs, order=order, thinking=thinking,
                                mode=mode, state=c.state)
            rec = _mk_rec(req_c, a, usage=usage, reasoning=reasoning)
            rec["session"] = session
            if gate_id:
                rec["gate_id"] = gate_id
            recs[c.id] = rec
        else:
            recs[c.id] = {"answers": a, "ms": 1}
    meta = {}
    if raw:
        meta = {"system_prompt_sha256": _sha_of(req),
                "diag": {"status": "complete", "session": session,
                         "sessions": [session]}}
    store.save(run, phase, {"meta": meta, "cases": recs})


class TestAnalysis(TmpStore):
    def test_clusters_group_translations(self):
        cl = qs_mod._clusters(["triage_es", "triage_en"])
        multi = [m for m in cl.values() if len(m) > 1]
        self.assertTrue(multi)
        self.assertTrue(all(len(m) == 2 for m in multi))
        phs = {p for m in multi for p, _ in m}
        self.assertEqual(phs, {"triage_es", "triage_en"})

    def test_paired_delta_all_hit_vs_all_miss(self):
        for ph in ("triage_es", "triage_en"):
            _write_run("run_f", ph, hit=False)
            _write_run("run_t", ph, hit=True)
        d = qs_mod.paired_delta("run_f", "run_t", iters=500, seed=1)
        self.assertIsNotNone(d)
        self.assertGreater(d["delta"], 50)
        self.assertGreater(d["lo"], 5)
        self.assertEqual(d["phases"], ["triage_es", "triage_en"])

    def test_paired_delta_seed_deterministic(self):
        _write_run("run_a", "triage_es", hit=True)
        _write_run("run_b", "triage_es", hit=True)
        d1 = qs_mod.paired_delta("run_a", "run_b", iters=200, seed=7)
        d2 = qs_mod.paired_delta("run_a", "run_b", iters=200, seed=7)
        self.assertEqual(d1["lo"], d2["lo"])
        self.assertAlmostEqual(d1["delta"], 0.0, places=7)

    def test_paired_delta_none_without_phases(self):
        self.assertIsNone(qs_mod.paired_delta("nope_a", "nope_b", iters=10))

    def test_range_boot(self):
        for ph in ("triage_es", "triage_en"):
            for r in ("r0", "r1", "r2", "r3"):
                _write_run(r, ph, hit=(r != "r3"))
        rb = qs_mod.range_boot(["r0", "r1", "r2", "r3"], iters=300, seed=1)
        self.assertIsNotNone(rb)
        self.assertGreater(rb["range"], 0)

    def test_primacy_subset_regla(self):
        """La regla textual reproduce la lista prefijada de R13 (37
        registros, 35 ids; sha congelado 4e7e2877f27d)."""
        subset = qs_mod.primacy_subset()
        self.assertEqual(len(subset), 37)
        self.assertEqual(len({cid for _, cid in subset}), 35)
        self.assertEqual(qs_mod.primacy_sha(subset), "4e7e2877f27d")

    def test_primacy_analysis(self):
        for ph in ("triage_es", "triage_en", "triage_ext_es",
                   "triage_ext_en", "adv1", "adv2", "adv3", "adv4", "adv5"):
            _write_run("f0", ph, hit=False)
            _write_run("f1", ph, hit=True)
            _write_run("f2", ph, hit=True)
            _write_run("f3", ph, hit=False)
        pa = qs_mod.primacy_analysis({"d0": "f0", "d1": "f1", "d2": "f2",
                                      "d3": "f3"}, iters=300, seed=1)
        self.assertEqual(pa["n_paired"], 37)
        self.assertGreater(pa["delta_pp"], 50)
        self.assertGreater(pa["lo"], 0)
        self.assertEqual(len(pa["holm"]), 7)

    def test_s202_agreement(self):
        for ph in ("papers32", "adv3"):
            _write_run("f0", ph, hit=True)
            _write_run("s202", ph, hit=True)
        k, n, p, lo, hi = qs_mod.s202_agreement("f0", "s202")
        self.assertEqual(k, n)
        self.assertGreater(n, 0)
        self.assertGreater(lo, 0)

    def test_p712_analysis_sintetico(self):
        qs, cases = load_phase("triage_es")
        sel = [c for c in cases
               if c.id in ("T01_ebus_alergia", "T02_factura_duplicada")]
        pcs = [("triage_es", c) for c in sel]
        for v in ("v1", "v3", "v5"):
            for r in (1, 2, 3):
                run = qs_mod.diag_run(v, r)
                recs = {}
                for c in sel:
                    a = (_answers_hit(qs, c.gt) if v != "v1"
                         else _answers_miss(qs, c.gt))
                    recs[c.id] = {"answers": a, "ms": 1}
                store.save(run, "triage_es", {"meta": {}, "cases": recs})
        with mock.patch.object(qs_mod, "p712_cases", return_value=pcs):
            pa = qs_mod.p712_analysis(iters=300, seed=1)
        self.assertGreater(pa["boot"]["v3"]["delta"], 50)
        self.assertGreater(pa["boot"]["v3"]["lo"], 10)

    def test_p712_manifesto_missing_explicit(self):
        """Un id del manifiesto que ya no existe en la batería aborta
        explícito, nunca silencioso (P02 se retiró en GT v4)."""
        with mock.patch.object(qs_mod, "P712_CASES",
                               [("adv1", "NO_EXISTE_XYZ")]):
            with self.assertRaises(SystemExit):
                qs_mod.p712_cases()

    def test_holm_cells(self):
        _write_run("fa", "triage_es", hit=True)
        _write_run("fb", "triage_es", hit=False)
        rows = qs_mod.holm_cells("fa", "fb")
        self.assertEqual(len(rows), 53)   # la familia Holm fijada en R13
        dept = next(r for r in rows if r["cell"] == "triage_es.department")
        self.assertEqual(dept["b"] + dept["c"], 14)

    def test_audit_evaluability(self):
        """Un run completo CON evidencia por caso (raw + usage + cliente +
        puerta resoluble) es evaluable; sin ella no."""
        cell = _fake_cell()
        key = qs_mod.cell_gate_key(cell)
        gid = f"gate_qwen_{key}@t~u1"
        _write_gate_archive(key, gid, hist=_default_hist())
        _write_run("t_run", "triage_es", hit=True, raw=True, gate_id=gid)
        with mock.patch.object(qs_mod.j67, "load_token_ref",
                               _default_hist):
            aud = qs_mod._audit_cell("T", cell)
        self.assertEqual(aud["n_ok"], 14)
        self.assertTrue(aud["evaluable"], aud)

    def test_audit_sin_raw_no_evaluable(self):
        """R16 §3: respuestas sin raw no acreditan visibilidad — la
        auditoría las contabiliza, no las omite."""
        cell = _fake_cell(run="noraw_run")
        gid = f"gate_qwen_{qs_mod.cell_gate_key(cell)}@t~u1"
        _write_gate_archive(qs_mod.cell_gate_key(cell), gid,
                            hist=_default_hist())
        _write_run("noraw_run", "triage_es", hit=True, gate_id=gid)
        with mock.patch.object(qs_mod.j67, "load_token_ref",
                               _default_hist):
            aud = qs_mod._audit_cell("T", cell)
        self.assertFalse(aud["evaluable"])
        self.assertEqual(len(aud["no_raw"]), 14)

    def test_audit_error_cuenta_como_sin_evidencia(self):
        """R16 §3: un caso con error es cobertura ausente, no un caso que
        la auditoría pueda descartar."""
        cell = _fake_cell(run="one_err")
        key = qs_mod.cell_gate_key(cell)
        gid = f"gate_qwen_{key}@t~u1"
        _write_gate_archive(key, gid, hist=_default_hist())
        _write_run("one_err", "triage_es", hit=True, raw=True, gate_id=gid)
        doc = store.load("one_err", "triage_es")
        cid = next(iter(doc["cases"]))
        doc["cases"][cid] = {"error": "boom"}
        store.save("one_err", "triage_es", doc)
        with mock.patch.object(qs_mod.j67, "load_token_ref",
                               _default_hist):
            aud = qs_mod._audit_cell("T", cell)
        self.assertFalse(aud["evaluable"])
        self.assertEqual(aud["errors"]["other"], 1)
        self.assertEqual(len(aud["missing"]), 1)

    def test_audit_sin_puerta_resoluble_no_evaluable(self):
        """Un caso cuyo gate_id no resuelve a una puerta ok de su sesión no
        está autorizado."""
        cell = _fake_cell(run="nogate")
        _write_run("nogate", "triage_es", hit=True, raw=True,
                   gate_id="gate_qwen_prob_typesafe_off_d0@t~fantasma")
        with mock.patch.object(qs_mod.j67, "load_token_ref",
                               _default_hist):
            aud = qs_mod._audit_cell("T", cell)
        self.assertFalse(aud["evaluable"])
        self.assertEqual(len(aud["gate_bad"]), 14)

    def test_mcnemar_una_version_por_traduccion(self):
        """R16 §9 + R13 §5: los seis McNemar de pares de órdenes y el de
        primacía usan UNA versión por caso traducido (convención ES; las
        fases adv* solo existen en un idioma) — las traducciones no son
        réplicas independientes en el test de hipótesis."""
        for n in ("d0", "d1", "d2", "d3"):
            for ph in qs_mod.PHASES_ALL:
                _write_run(n, ph, hit=(n != "d0"))
        lens = []
        orig = metrics.mcnemar

        def spy(a, b):
            lens.append(len(a))
            return orig(a, b)

        with mock.patch.object(metrics, "mcnemar", side_effect=spy):
            qs_mod.primacy_analysis(
                {n: n for n in ("d0", "d1", "d2", "d3")}, iters=20)
        self.assertEqual(len(lens), 7)   # primacía + 6 pares
        es_n = len({c.id for ph in qs_mod.PHASES_ALL
                    if "department" in load_phase(ph)[0]
                    and (ph.endswith("_es") or ph.startswith("adv"))
                    for c in load_phase(ph)[1]})
        self.assertEqual(lens[0], 35)    # primacía = subconjunto prefijado
        self.assertEqual(sorted(lens[1:]), [es_n] * 6)

    def test_discrete_offsets_persistidos_en_run(self):
        """R16 §8: los offsets medidos por la puerta viajan al diag del
        propio run (con su entry de puerta) — la auditoría no depende de
        una puerta mutable."""
        cell = _fake_cell(run="disc_run", mode="discrete")
        cells = {"T": cell}
        ctx = _ctx(cells, model=_StubModel(mode="discrete"))
        key = qs_mod.cell_gate_key(cell)
        gid = "gate_qwen_disc_typesafe_off_d0@t~uD"
        ctx["gate_ids"][key] = gid
        ctx["gate_entries"][key] = {"gate_id": gid, "ok": True,
                                    "session": "s1",
                                    "offsets": {"triageadv": 0}}
        ctx["offsets"][key] = {"triageadv": 0}
        qs_mod._exec_slot(ctx, "T", "triage_es", False,
                          mock.Mock(return_value=0.0), lambda s: None,
                          lambda *a, **k: None)
        self.assertFalse(ctx["cell_stop"], ctx["cell_stop"])
        doc = store.load("disc_run", "triage_es")
        self.assertEqual(doc["meta"]["diag"]["offsets_familia"],
                         {"triageadv": 0})
        self.assertEqual(doc["meta"]["diag"]["gate"]["gate_id"], gid)
        _write_gate_archive(key, gid, offsets={"triageadv": 0},
                            hist=_default_hist())
        with mock.patch.object(qs_mod.j67, "load_token_ref",
                               _default_hist):
            aud = qs_mod._audit_cell("T", cell)
        self.assertEqual(aud["token_violations"], [])
        self.assertTrue(aud["evaluable"], aud)


class TestAnalyzeEvaluable(TmpStore):
    """R16 §7: las clasificaciones exigen runs EVALUABLES (cobertura
    completa + evidencia por caso + puerta que los autorizó); existir en
    disco no basta."""

    def test_s202_exige_runs_evaluables(self):
        """La sonda de R16: dos runs de disco sin raw ni puertas daban
        'S202 CONFIRMADA (107/107 1.000)'. Ahora NO EVALUABLE."""
        for name in ("F0", "S202"):
            for ph in qs_mod.CELLS[name]["phases"]:
                _write_run(qs_mod.CELLS[name]["run"], ph, hit=True)
        with mock.patch.object(qs_mod.j67, "load_token_ref",
                               lambda: {}):
            rep = qs_mod.analyze(iters=20, printer=lambda *a: None)
        cls = rep["classification"]["S202 acuerdo >=97%"]
        self.assertTrue(cls.startswith("NO EVALUABLE"), cls)

    def test_p712_cobertura_parcial_no_evaluable(self):
        """La sonda de R16: solo los 2 casos de triage_es en disco sin
        evidencia → antes CONFIRMADA con Δ=100 sobre 10 null."""
        for v in qs_mod.DIAG_VARIANTS:
            for r in (1, 2, 3):
                _write_run(qs_mod.diag_run(v, r), "triage_es",
                           hit=(v != "v1"))
        with mock.patch.object(qs_mod.j67, "load_token_ref",
                               lambda: {}):
            rep = qs_mod.analyze(iters=20, printer=lambda *a: None)
        cls = rep["classification"]
        self.assertTrue(cls["P71.2 frases visibles >=10pp"]
                        .startswith("NO EVALUABLE"), cls)
        self.assertFalse(any(
            k.startswith("P71.2 V") and v.startswith("CONFIRMADA")
            for k, v in cls.items()))

    def test_p712_evaluable_confirma(self):
        """Con los 9 runs completos y acreditados (raw, sha, puerta y
        referencias), la clasificación llega a CONFIRMADA."""
        key_of = {"v1": "prob_typesafe_off_d0",
                  "v3": "prob_sin_antinj_off_d0",
                  "v5": "prob_antinj_alt_off_d0"}
        hist = {}
        for ph, cid in qs_mod.P712_CASES:
            hist.setdefault(ph, {})[cid] = 10
        refs = {ph: {c.id: 10 for c in load_phase(ph)[1]}
                for ph in sorted({p for p, _ in qs_mod.P712_CASES})}
        for v, key in key_of.items():
            gid = f"gate_qwen_{key}@t~u_{v}"
            # v3/v5 necesitan referencias tokenizer: van archivadas en la
            # evidencia inmutable de SU puerta (R17 §5); v1 congela la
            # histórica (R18 §1)
            if v == "v1":
                _write_gate_archive(key, gid, hist=hist)
            else:
                _write_gate_archive(key, gid, refs_doc={
                    "meta": {"combo": key}, "tokens": refs})
            for r in (1, 2, 3):
                for ph in sorted({p for p, _ in qs_mod.P712_CASES}):
                    _write_run(qs_mod.diag_run(v, r), ph, hit=(v != "v1"),
                               raw=True, gate_id=gid, usage=10)
        with mock.patch.object(qs_mod.j67, "load_token_ref",
                               lambda: hist), \
             mock.patch.object(qs_mod, "load_refs", lambda k: refs):
            rep = qs_mod.analyze(iters=50, printer=lambda *a: None)
        cls = rep["classification"]
        self.assertTrue(cls["P71.2 V3 >=10pp"].startswith("CONFIRMADA"),
                        cls)
        self.assertTrue(cls["P71.2 V5 >=10pp"].startswith("CONFIRMADA"),
                        cls)
        self.assertTrue(rep["p712"]["complete"])
        self.assertIn("secondary", rep["p712"])


# ------------------------------------------ salidas descriptivas §8 (R28)

class TestDescriptivos(TmpStore):
    """Salidas descriptivas del análisis exigidas por el pre-registro §8
    (hallazgo R28 §2): vectores crudos nulos/formato con IDs, latencia y
    tokens por celda, desglose por pregunta de P71.1, baselines de mayoría
    y detalle de la primacía — ninguna cambia clasificaciones."""

    def _write_wire_run(self, run, phase, wire, ms=100, prompt=10,
                        completion=5, reasoning=0):
        """Run sintético cuyo raw lleva el formato wire real del servidor
        (vectores de probabilidad/escalares, no las respuestas
        normalizadas) y usage con desglose de tokens."""
        qs, cases = load_phase(phase)
        recs = {}
        for c in cases:
            resp = {"choices": [{"finish_reason": "stop",
                                 "message": {"content": json.dumps(
                                     {"answers": wire})}}],
                    "usage": {"prompt_tokens": prompt,
                              "completion_tokens": completion,
                              "reasoning_tokens": reasoning}}
            recs[c.id] = {"answers": wire, "ms": ms,
                          "raw": [{"request": {}, "llm_response": resp}],
                          "usage": {"input_tokens": prompt}}
        store.save(run, phase, {"meta": {}, "cases": recs})

    def test_raw_scan_detecta_nulos_con_ids(self):
        wire = {"department": {"admin": 0.9, "bronchoscopia": 0.05,
                               "urgencias": 0.03, "consulta_externa": 0.02},
                "urgency": {"0": 0.0, "1": 0.0, "2": 0.0},
                "clinical": 0.8, "hostile": 0.1, "same_day": 0.3}
        self._write_wire_run("scan_run", "triage_es", wire)
        s = qs_mod._raw_scan("scan_run", ["triage_es"], "probabilities")
        want = [f"triage_es/{c.id}.urgency"
                for c in load_phase("triage_es")[1]]
        self.assertEqual(s["nulos"], want)
        self.assertEqual(s["invalidos"], [])
        self.assertEqual(s["uniformes"], [])
        self.assertEqual(s["ok"], 14 * 5 - 14)
        self.assertEqual(s["n_casos"], 14)
        self.assertEqual(s["intentos"], 14)

    def test_raw_scan_invalid_sin_respuesta_y_sin_raw(self):
        """Un vector que no cubre las claves es `invalid`; un intento no
        parseable y un caso sin raw se reportan aparte — ninguno cuenta
        como cero nulos."""
        wire = {"department": {"admin": 1.0},
                "urgency": {"0": 0.5, "1": 0.3, "2": 0.2},
                "clinical": 0.8, "hostile": 0.1, "same_day": 0.3}
        self._write_wire_run("scan2", "triage_es", wire)
        doc = store.load("scan2", "triage_es")
        c0, c1, c2 = [c.id for c in load_phase("triage_es")[1][:3]]
        msg = doc["cases"][c0]["raw"][0]["llm_response"]["choices"][0]\
            ["message"]
        msg["content"] = "no json"
        del doc["cases"][c1]["raw"]
        doc["cases"][c2] = {"error": "boom"}
        store.save("scan2", "triage_es", doc)
        s = qs_mod._raw_scan("scan2", ["triage_es"], "probabilities")
        self.assertEqual(s["sin_respuesta"], [f"triage_es/{c0}#1"])
        self.assertEqual(s["sin_raw"], [f"triage_es/{c1}"])
        self.assertEqual(s["sin_registro"], [f"triage_es/{c2}"])
        self.assertEqual(len(s["invalidos"]), 14 - 3)
        self.assertTrue(all(t.endswith(".department")
                            for t in s["invalidos"]))
        self.assertEqual(s["nulos"], [])

    def test_raw_scan_discrete_invalid(self):
        wire = {"department": "etiqueta_inventada", "urgency": 2,
                "clinical": True, "hostile": False, "same_day": True}
        self._write_wire_run("scan3", "triage_es", wire)
        s = qs_mod._raw_scan("scan3", ["triage_es"], "discrete")
        self.assertEqual(len(s["invalidos"]), 14)
        self.assertTrue(all(t.endswith(".department")
                            for t in s["invalidos"]))
        self.assertEqual(s["nulos"], [])

    def test_usage_stats_media_mediana_tokens(self):
        self._write_wire_run("u_run", "triage_es", {}, ms=100, prompt=10,
                             completion=5, reasoning=2)
        doc = store.load("u_run", "triage_es")
        for i, rec in enumerate(doc["cases"].values()):
            rec["ms"] = 100 if i % 2 == 0 else 300
        store.save("u_run", "triage_es", doc)
        s = qs_mod._usage_stats("u_run", ["triage_es"])
        self.assertEqual(s["n"], 14)
        self.assertEqual(s["ms_media"], 200)
        self.assertEqual(s["ms_mediana"], 200)
        self.assertEqual(s["ms_total"], 2800)
        self.assertEqual(s["prompt_tokens"], 140)
        self.assertEqual(s["completion_tokens"], 70)
        self.assertEqual(s["razonamiento_tokens"], 28)
        self.assertEqual(s["coste_api"], 0)

    def test_p711_breakdown_reglas_separadas(self):
        """Las reglas se reportan por separado: en urgency el `score`
        declarado puede acertar donde el argmax del vector no (y al
        revés); noul va por prob cruda ≥0.5, choice por etiqueta/argmax."""
        qs, cases = load_phase("triage_es")
        f0, d0 = {}, {}
        n_argmax_hit = sum(1 for c in cases if c.gt["urgency"] == 2)
        for c in cases:
            a = _answers_hit(qs, c.gt)
            # score declarado correcto; el vector concentra la moda en 2
            a["urgency"] = {"score": float(c.gt["urgency"]),
                            "probabilities": {"0": 0.1, "1": 0.1,
                                              "2": 0.8}}
            f0[c.id] = {"answers": a, "ms": 1}
            d0[c.id] = {"answers": _answers_miss(qs, c.gt), "ms": 1}
        store.save("p7_f0", "triage_es", {"meta": {}, "cases": f0})
        store.save("p7_d0", "triage_es", {"meta": {}, "cases": d0})
        b = qs_mod._p711_breakdown("p7_f0", "p7_d0")
        self.assertEqual(set(b), {"same_day", "urgency", "department"})
        e = b["urgency"]
        self.assertEqual(e["n"], 14)
        self.assertEqual(e["F0"]["score"]["aciertos"], 14)
        self.assertEqual(e["F0"]["argmax"]["aciertos"], n_argmax_hit)
        self.assertEqual(e["D0"]["score"]["aciertos"], 0)
        s = b["same_day"]
        self.assertEqual(s["tipo"], "noul")
        self.assertEqual(s["F0"]["prob>=0.5"]["aciertos"], 14)
        self.assertEqual(s["D0"]["prob>=0.5"]["aciertos"], 0)
        self.assertIn("prob_media_F0", s)
        d = b["department"]
        self.assertEqual(d["F0"]["choice"]["aciertos"], 14)
        self.assertEqual(d["F0"]["argmax"]["aciertos"], 14)

    def test_baseline_table_gt(self):
        t = qs_mod._baseline_table(["triage_es", "adv1"])
        self.assertEqual(set(t), set(qs_mod.PHASES_ALL))
        self.assertTrue(t["ood"]["baseline_saturada"])
        self.assertTrue(t["triage_es"]["usada_en_agregado"])
        self.assertFalse(t["adv2"]["usada_en_agregado"])
        b = score.baseline("triage_es")
        self.assertEqual(t["triage_es"]["pct"], b["pct"])
        self.assertEqual(t["triage_es"]["mayoria"]["department"]
                         ["respuesta"], b["answers"]["department"])

    def test_primacy_error_ids(self):
        """El detalle de primacía (R28 §2): errores por orden sobre el
        subconjunto congelado con los IDs explícitos de cada fallo."""
        for ph in ("triage_es", "triage_en", "triage_ext_es",
                   "triage_ext_en", "adv1", "adv2", "adv3", "adv4",
                   "adv5"):
            _write_run("f0", ph, hit=False)
            _write_run("f1", ph, hit=True)
            _write_run("f2", ph, hit=True)
            _write_run("f3", ph, hit=True)
        pa = qs_mod.primacy_analysis({"d0": "f0", "d1": "f1", "d2": "f2",
                                      "d3": "f3"}, iters=20, seed=1)
        self.assertEqual(len(pa["error_ids"]["d0"]), pa["errors"]["d0"])
        self.assertEqual(len(pa["error_ids"]["d0"]), pa["n_paired"])
        self.assertEqual(pa["error_ids"]["d1"], [])
        self.assertTrue(all("/" in t for t in pa["error_ids"]["d0"]))
        self.assertEqual(sorted(f"{p}/{c}" for p, c in pa["subset"]),
                         sorted(pa["error_ids"]["d0"]))

    def test_analyze_emite_descriptivos(self):
        """Las salidas descriptivas se calculan sobre todo run presente
        (evaluable o no) y las clasificaciones quedan intactas."""
        for name in ("F0", "D0"):
            for ph in qs_mod.CELLS[name]["phases"]:
                _write_run(qs_mod.CELLS[name]["run"], ph, hit=True,
                           raw=True, usage=10)
        with mock.patch.object(qs_mod.j67, "load_token_ref",
                               lambda: {}):
            rep = qs_mod.analyze(iters=20, printer=lambda *a: None)
        d = rep["descriptivos"]
        for k in ("vectores_crudos", "latencia_tokens",
                  "p711_por_pregunta", "baselines"):
            self.assertIn(k, d)
        self.assertEqual(d["vectores_crudos"]["F0"]["n_casos"], 194)
        self.assertEqual(d["latencia_tokens"]["F0"]["coste_api"], 0)
        self.assertIsNone(d["latencia_tokens"]["F0"]["ms_media"])
        self.assertEqual(d["latencia_tokens"]["F0"]["prompt_tokens"],
                         1940)
        self.assertEqual(d["p711_por_pregunta"]["same_day"]["n"], 160)
        self.assertIn("P71.1 discrete >=+10 sobre F0",
                      rep["classification"])

    def test_analyze_descriptivos_sin_runs(self):
        """Sin runs en disco las secciones salen vacías y las
        clasificaciones NO EVALUABLE; nada se inventa."""
        with mock.patch.object(qs_mod.j67, "load_token_ref",
                               lambda: {}):
            rep = qs_mod.analyze(iters=20, printer=lambda *a: None)
        d = rep["descriptivos"]
        self.assertEqual(d["vectores_crudos"], {})
        self.assertEqual(d["latencia_tokens"], {})
        self.assertNotIn("p68_on_off", d)
        self.assertNotIn("p711_por_pregunta", d)
        self.assertEqual(set(d["baselines"]), set(qs_mod.PHASES_ALL))
        for v in rep["classification"].values():
            self.assertTrue(v.startswith("NO EVALUABLE"), v)


# ------------------------------------------------------- correcciones R17

class TestR17ElapsedMonotono(TmpStore):
    def test_elapsed_persistido_monotono_tras_slot(self):
        """R17 §1 (sonda): un slot completo deja el tiempo consumido en
        disco — elapsed_s ya no vuelve al valor base al cerrar el slot — y
        una interrupción entre slots no pierde el bloque en curso."""
        clock = [0.0]

        class Timed(_StubModel):
            def decide(self, *a):
                clock[0] += 1.0
                return super().decide(*a)

        cells = {"T": _fake_cell(run="elapsed")}
        ctx = _ctx(cells, model=Timed())
        qs_mod._save_state(ctx["st"])
        escritos = []
        orig = qs_mod._save_state

        def spy(st):
            orig(st)
            escritos.append(qs_mod._load_state()["elapsed_s"])

        with mock.patch.object(qs_mod, "_save_state", side_effect=spy):
            qs_mod._exec_slot(ctx, "T", "triage_es", False,
                              lambda: clock[0], lambda s: None,
                              lambda *a, **k: None)
        saved = qs_mod._load_state()
        # cierre/reanudación justo tras el slot: el acumulado no retrocede
        self.assertEqual(saved["elapsed_s"], 14.0)
        self.assertEqual(saved["cell_s"]["T"], 14.0)
        self.assertEqual(saved["requests"], 14)
        # y nunca retrocedió en ningún guardado intermedio
        self.assertEqual(escritos, sorted(escritos))
        self.assertEqual(escritos[-1], 14.0)


class TestR17Budgets(TmpStore):
    def test_health_sondas_contra_tope_de_peticiones(self):
        """R17 §2 (sonda): las sondas de /health son peticiones — se
        verifican contra el tope duro; sin cupo no se abre ni una."""
        class Timeout(_StubModel):
            def decide(self, *a):
                e = TimeoutError("timeout")
                e.diag = {"attempts": 3}
                raise e

        cells = {"T": _fake_cell(run="healthcap")}
        model = Timeout()
        ctx = _ctx(cells, model=model)
        ctx["st"]["requests"] = qs_mod.REQUEST_CAP - 3
        calls = []
        with mock.patch.object(qs_mod, "health_ok",
                               side_effect=lambda u, timeout=None:
                               calls.append(u) or False):
            qs_mod._exec_slot(ctx, "T", "triage_es", False,
                              lambda: 0.0, lambda s: None,
                              lambda *a, **k: None)
        # el caso consumió sus 3 intentos (hasta 5000): ninguna sonda llega
        # a abrirse
        self.assertEqual(calls, [])
        self.assertEqual(ctx["st"]["requests"], qs_mod.REQUEST_CAP)
        self.assertIsNotNone(ctx["session_stop"])
        self.assertEqual(qs_mod._load_state()["requests"],
                         qs_mod.REQUEST_CAP)

    def test_health_sondas_contabilizan_peticiones(self):
        """Con algo de cupo las sondas se abren, pero cada una se asienta
        en disco y el tope sigue siendo duro."""
        class Timeout(_StubModel):
            def decide(self, *a):
                e = TimeoutError("timeout")
                e.diag = {"attempts": 1}
                raise e

        cells = {"T": _fake_cell(run="healthcount")}
        ctx = _ctx(cells, model=Timeout())
        ctx["st"]["requests"] = qs_mod.REQUEST_CAP - 3
        calls = []
        with mock.patch.object(qs_mod, "health_ok",
                               side_effect=lambda u, timeout=None:
                               calls.append(u) or False):
            qs_mod._exec_slot(ctx, "T", "triage_es", False,
                              lambda: 0.0, lambda s: None,
                              lambda *a, **k: None)
        # tras el caso quedan 4998; dos sondas sí, la tercera ya no cabe
        self.assertEqual(len(calls), 2)
        self.assertEqual(ctx["st"]["requests"], qs_mod.REQUEST_CAP)
        self.assertIsNotNone(ctx["session_stop"])

    def test_health_deadline_acotado_por_sesion(self):
        """R17 §2: la espera de salud se acota con el remanente de sesión
        y de celda, recalculado tras el caso — no con el spent previo."""
        class Timeout(_StubModel):
            def decide(self, *a):
                e = TimeoutError("timeout")
                e.diag = {"attempts": 1}
                raise e

        cells = {"T": _fake_cell(run="healthdl")}
        ctx = _ctx(cells, model=Timeout())
        ctx["st"]["elapsed_s"] = qs_mod.SESSION_CAP_S - 30
        ctx["elapsed_base"] = ctx["st"]["elapsed_s"]
        deadlines = []

        def fake_wait(urls, deadline, **kw):
            deadlines.append(deadline)
            return False, {}

        with mock.patch.object(qs_mod, "wait_health",
                               side_effect=fake_wait):
            qs_mod._exec_slot(ctx, "T", "triage_es", False,
                              lambda: 0.0, lambda s: None,
                              lambda *a, **k: None)
        self.assertEqual(deadlines, [30.0])
        self.assertIsNotNone(ctx["session_stop"])

    def test_sin_tiempo_de_sesion_no_abre_peticion(self):
        """R17 §2: con el tope de sesión agotado no se abre ni un caso."""
        model = _StubModel()
        st = {"session": "s1", "started": "x",
              "elapsed_s": qs_mod.SESSION_CAP_S, "requests": 0,
              "cell_s": {}, "retried": {}, "sessions": ["s1"]}
        ctx, out = self._mk_slot(st=st, model=model)
        self.assertEqual(model.calls, 0)
        self.assertEqual(ctx["session_stop"], "tope de sesión de 10 h")

    def _mk_slot(self, **ctxkw):
        cells = {"T": _fake_cell()}
        ctx = _ctx(cells, **ctxkw)
        qs_mod._exec_slot(ctx, "T", "triage_es", False,
                          mock.Mock(return_value=0.0), lambda s: None,
                          lambda *a, **k: None)
        return ctx, None


class TestR17ReservaDurable(TmpStore):
    def test_crash_en_retry_deja_reserva_y_marca(self):
        """R17 §3 (sonda): KeyboardInterrupt con la petición del reintento
        en curso — reserva, operación pendiente y marca del reintento
        único ya estaban en disco; al reanudar no se repite ni se pierde
        el consumo."""
        class Interrupted(_StubModel):
            def decide(self, *a):
                raise KeyboardInterrupt("crash during request")

        cells = {"T": _fake_cell(run="crash")}
        ctx = _ctx(cells, model=Interrupted())
        qs_mod._save_state(ctx["st"])
        first = load_phase("triage_es")[1][0].id
        store.save("crash", "triage_es",
                   {"meta": {}, "cases": {first: {"error": "previous"}}})
        with self.assertRaises(KeyboardInterrupt):
            qs_mod._exec_slot(ctx, "T", "triage_es", True,
                              lambda: 0.0, lambda s: None,
                              lambda *a, **k: None)
        saved = qs_mod._load_state()
        # la reserva (retries+1) quedó asentada antes de abrir la petición
        self.assertEqual(saved["requests"], 3)
        # la marca del reintento único se guardó ANTES de ejecutarlo
        self.assertEqual(saved["retried"]["crash/triage_es"], [first])
        self.assertEqual(saved["pending"]["case"], first)
        self.assertEqual(saved["pending"]["reserved"], 3)
        # reanudación: el reintento único ya está consumido y la reserva
        # sigue contabilizada — ni se repite el caso ni se pierde el gasto
        m2 = _StubModel()
        ctx2 = _ctx(cells, model=m2)
        ctx2["st"] = qs_mod._load_state()
        ctx2["elapsed_base"] = ctx2["st"]["elapsed_s"]
        qs_mod._exec_slot(ctx2, "T", "triage_es", True,
                          lambda: 0.0, lambda s: None,
                          lambda *a, **k: None)
        self.assertEqual(m2.calls, 0)
        self.assertEqual(ctx2["st"]["requests"], 3)
        rec = store.load("crash", "triage_es")["cases"][first]
        self.assertIn("error", rec)

    def test_reserva_se_concilia_al_completar(self):
        """La reserva se libera al conciliar: un caso resuelto al primer
        intento solo descuenta 1 petición, no las 3 reservadas."""
        cells = {"T": _fake_cell(run="reconcile")}
        ctx = _ctx(cells, model=_StubModel())
        qs_mod._exec_slot(ctx, "T", "triage_es", False,
                          lambda: 0.0, lambda s: None, lambda *a, **k: None)
        self.assertEqual(qs_mod._load_state()["requests"], 14)
        self.assertIsNone(qs_mod._load_state().get("pending"))


class TestR17Timeouts(TmpStore):
    def test_timeout_operativo_sin_mutar_config(self):
        """R17 §4: la cota de tiempo restante viaja por el deadline
        externo del proveedor — timeout/case_timeout del modelo no se
        tocan y el meta guardado sigue siendo la config congelada, así la
        reanudación es compatible."""
        class Limits(_StubModel):
            def __init__(self):
                super().__init__()
                self.timeout = 300.0
                self.case_timeout = 600.0

            def meta(self):
                return {**super().meta(), "timeout": self.timeout,
                        "case_timeout": self.case_timeout}

        cells = {"T": _fake_cell(run="limits", budget_s=5)}
        model = Limits()
        ctx = _ctx(cells, model=model)
        qs_mod._exec_slot(ctx, "T", "triage_es", False,
                          lambda: 0.0, lambda s: None, lambda *a, **k: None)
        self.assertEqual(model.timeout, 300.0)
        self.assertEqual(model.case_timeout, 600.0)
        doc = store.load("limits", "triage_es")
        self.assertEqual(doc["meta"]["timeout"], 300.0)
        self.assertEqual(doc["meta"]["case_timeout"], 600.0)
        fresh = _ctx(cells, model=Limits())
        fresh["st"] = ctx["st"]
        qs_mod._validate_existing(fresh, cells, ["T"], lambda *a: None)

    @unittest.skipUnless(HAS_LIB, "necesita system-one-adapter (.venv-llm)")
    def test_timeout_operativo_adaptador_real(self):
        """R17 §4 con el adaptador real frente a servidor falso (sonda de
        la revisión): remanente de celda=5 s, la petición corre con el
        deadline externo sin mutar opts; meta guarda 300/600 y la
        reanudación fresca no aborta."""
        from jevbench.adapters.llm import LLM
        from tests.test_llm_adapter import FakeOpenAIServer
        from tests.test_llm_adapter import _chat_completion
        resp = _chat_completion(json.dumps({"answers": ANSWERS}))
        resp["usage"]["prompt_tokens"] = 10
        with FakeOpenAIServer(lambda n, b: {"json": resp}) as server:
            cell = _fake_cell(run="actual_llm", budget_s=5)
            cells = {"T": cell}

            def mk():
                return LLM(**{**qs_mod._cell_opts(cell),
                              "base_url": server.base_url})

            model = mk()
            ctx = _ctx(cells, model=model)
            q, cs = load_phase("triage_es")
            with mock.patch.object(qs_mod, "load_phase",
                                   return_value=(q, cs[:1])):
                qs_mod._exec_slot(ctx, "T", "triage_es", False,
                                  lambda: 0.0, lambda s: None,
                                  lambda *a, **k: None)
            # el deadline operativo llegó al proveedor (5 s de remanente)
            self.assertIsNotNone(model.target._ext_deadline)
            doc = store.load("actual_llm", "triage_es")
            self.assertEqual(doc["meta"]["timeout"], 300.0)
            self.assertEqual(doc["meta"]["case_timeout"], 600.0)
            fresh = _ctx(cells, model=mk())
            fresh["st"] = ctx["st"]
            qs_mod._validate_existing(fresh, cells, ["T"],
                                      lambda *a: None)
            self.assertEqual(len(server.httpd.requests), 1)


class TestR17GateRefs(TmpStore):
    """R17 §5: las referencias de tokens quedan ligadas a la puerta que
    las autorizó — si cambian después, la puerta deja de valer y los casos
    se invalidan."""

    def _combo_cell(self):
        return _fake_cell(run="ref_drift", thinking=True)

    def _setup_drift(self):
        """La sonda de R17: puerta aprobada con referencia de 100 tokens y
        luego el fichero cambia a 10 tokens."""
        cell = self._combo_cell()
        key = qs_mod.cell_gate_key(cell)
        gid = f"gate_qwen_{key}@t~u"
        rp = qs_mod._refs_path(key)
        rp.parent.mkdir(parents=True, exist_ok=True)
        doc = {"meta": {"combo": key},
               "tokens": {"triage_es": {c.id: 100
                                       for c in load_phase("triage_es")[1]}}}
        rp.write_text(json.dumps(doc))
        entry = {"gate_id": gid, "session": "s1", "ts": "t", "ok": True,
                 "refs": {"file": rp.name,
                          "sha256": hashlib.sha256(rp.read_bytes())
                          .hexdigest()[:12]}}
        store.save(f"gate_qwen_{key}", "adv1",
                   {"meta": {"diag": {"latest_gate": entry,
                                      "gate_history": [entry]}},
                    "cases": {}})
        # la referencia cambia DESPUÉS de la puerta
        doc["tokens"]["triage_es"] = {c.id: 10
                                      for c in load_phase("triage_es")[1]}
        rp.write_text(json.dumps(doc))
        _write_run(cell["run"], "triage_es", hit=True, raw=True,
                   gate_id=gid)
        rd = store.load(cell["run"], "triage_es")
        for r in rd["cases"].values():
            r["raw"][0]["request"]["chat_template_kwargs"][
                "enable_thinking"] = True
            r["raw"][0]["llm_response"]["choices"][0]["message"][
                "reasoning_content"] = "reasoning"
        store.save(cell["run"], "triage_es", rd)
        return cell, key, gid

    def test_referencia_cambiada_invalida_puerta_y_casos(self):
        cell, key, gid = self._setup_drift()
        ctx = _ctx({"T": cell}, model=_StubModel(thinking=True))
        # la puerta ya no vale: el fichero vigente no es el autorizado
        self.assertFalse(qs_mod._cell_gate_ok(ctx, cell))
        # y la auditoría no puede dar por buenos casos que la puerta no
        # acreditó con ESA referencia
        with mock.patch.object(qs_mod.j67, "load_token_ref",
                               _default_hist):
            aud = qs_mod._audit_cell("T", cell)
        self.assertFalse(aud["evaluable"])
        self.assertTrue(aud["gate_bad"] or aud["token_violations"], aud)

    def test_referencia_archivada_en_el_entry_se_respeta(self):
        """Formato completo: la auditoría corre contra la referencia
        archivada en el entry inmutable de la puerta de cada caso — no
        contra el fichero vigente."""
        cell = self._combo_cell()
        key = qs_mod.cell_gate_key(cell)
        gid = f"gate_qwen_{key}@t~u"
        archived = {"meta": {"combo": key},
                    "tokens": {"triage_es": {
                        c.id: 100 for c in load_phase("triage_es")[1]}}}
        # fichero vigente distinto del autorizado (10 tokens)
        rp = qs_mod._refs_path(key)
        rp.parent.mkdir(parents=True, exist_ok=True)
        rp.write_text(json.dumps(
            {"meta": {"combo": key},
             "tokens": {"triage_es": {
                 c.id: 10 for c in load_phase("triage_es")[1]}}}))
        _write_gate_archive(key, gid, refs_doc=archived)
        _write_run(cell["run"], "triage_es", hit=True, raw=True,
                   gate_id=gid, usage=10)
        rd = store.load(cell["run"], "triage_es")
        for r in rd["cases"].values():
            r["raw"][0]["request"]["chat_template_kwargs"][
                "enable_thinking"] = True
            r["raw"][0]["llm_response"]["choices"][0]["message"][
                "reasoning_content"] = "reasoning"
        store.save(cell["run"], "triage_es", rd)
        # los casos registraron 10 tokens pero la puerta autorizó 100:
        # violación de tokens contra la referencia de SU puerta
        with mock.patch.object(qs_mod.j67, "load_token_ref",
                               _default_hist):
            aud = qs_mod._audit_cell("T", cell)
        self.assertFalse(aud["evaluable"])
        self.assertEqual(len(aud["token_violations"]), 14)
        # y ejecutar con el fichero cambiado también se rechaza
        ctx = _ctx({"T": cell}, model=_StubModel(thinking=True))
        self.assertFalse(qs_mod._cell_gate_ok(ctx, cell))

    def test_referencia_intacta_permite_ejecutar(self):
        """Con el fichero vigente idéntico al archivado por la puerta, la
        celda sí queda habilitada y se vigila con la referencia de la
        puerta."""
        cell = self._combo_cell()
        key = qs_mod.cell_gate_key(cell)
        gid = f"gate_qwen_{key}@t~u"
        doc = {"meta": {"combo": key},
               "tokens": {"triage_es": {c.id: 10
                                       for c in load_phase("triage_es")[1]}}}
        rp = qs_mod._refs_path(key)
        rp.parent.mkdir(parents=True, exist_ok=True)
        rp.write_text(json.dumps(doc))
        _write_gate_archive(key, gid, refs_doc=doc)
        ctx = _ctx({"T": cell}, model=_StubModel(thinking=True))
        self.assertTrue(qs_mod._cell_gate_ok(ctx, cell))
        self.assertEqual(ctx["refs_on"][key]["triage_es"]["T01_ebus_alergia"],
                         10)


class TestR17Manifest(TmpStore):
    """R17 §6: el ejecutor carga y verifica el manifiesto congelado por el
    dry-run; el texto impreso cubre todo lo que el manifiesto congela."""

    def _cells_env(self):
        cells = {"T": _fake_cell()}
        patches = [
            mock.patch.object(qs_mod, "CELLS", cells),
            mock.patch.object(qs_mod, "_calendar",
                              lambda: [("T", "triage_es")]),
            mock.patch.object(qs_mod.j67, "load_token_ref",
                              _default_hist),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        return cells

    def _run_kw(self):
        return dict(session="s1", model_factory=lambda o: _StubModel(),
                    now=mock.Mock(return_value=0.0), printer=lambda *a: None)

    def test_run_requiere_manifiesto(self):
        self._cells_env()
        rc = qs_mod.run(**self._run_kw())
        self.assertEqual(rc, 1)
        self.assertIsNone(store.load("t_run", "triage_es"))

    def test_run_rechaza_manifiesto_cambiado(self):
        cells = self._cells_env()
        qs_mod._manifest_path().write_text(
            json.dumps(qs_mod._plan_manifest(), ensure_ascii=False))
        # cambiar el ejecutable tras congelar el plan (p. ej. los topes)
        # invalida el manifiesto antes de abrir peticiones
        with mock.patch.object(qs_mod, "REQUEST_CAP", 4999):
            rc = qs_mod.run(**self._run_kw())
        self.assertEqual(rc, 1)
        self.assertIsNone(store.load("t_run", "triage_es"))
        # y un manifiesto alterado a mano tampoco pasa
        man = json.loads(qs_mod._manifest_path().read_text())
        man["manifest_sha256"] = "0" * 16
        qs_mod._manifest_path().write_text(json.dumps(man))
        rc = qs_mod.run(**self._run_kw())
        self.assertEqual(rc, 1)
        self.assertIsNone(store.load("t_run", "triage_es"))

    def test_run_rechaza_refs_cambiadas_tras_congelar(self):
        """Las referencias también quedan congeladas en el manifiesto:
        crear/modificar el fichero de refs después del dry-run invalida la
        ejecución (hay que reimprimir el plan)."""
        cells = self._cells_env()
        qs_mod._manifest_path().write_text(
            json.dumps(qs_mod._plan_manifest(), ensure_ascii=False))
        key = "prob_sin_antinj_off_d0"   # combo diag que usa refs tokenizer
        rp = qs_mod._refs_path(key)
        rp.parent.mkdir(parents=True, exist_ok=True)
        rp.write_text(json.dumps({"meta": {"combo": key},
                                  "tokens": {"triage_es": {"T01": 10}}}))
        rc = qs_mod.run(**self._run_kw())
        self.assertEqual(rc, 1)
        self.assertIsNone(store.load("t_run", "triage_es"))

    def test_run_consumo_ok_y_hash_en_diag(self):
        cells = self._cells_env()
        man = qs_mod._plan_manifest()
        qs_mod._manifest_path().write_text(
            json.dumps(man, ensure_ascii=False))
        key = qs_mod.cell_gate_key(cells["T"])
        _write_gate_archive(key, "g@t", hist=_default_hist())
        rc = qs_mod.run(**self._run_kw())
        self.assertEqual(rc, 0)
        doc = store.load("t_run", "triage_es")
        self.assertEqual(doc["meta"]["diag"]["manifest_sha256"],
                         man["manifest_sha256"])

    def test_dry_run_exporta_e_imprime_todo(self):
        """El texto del dry-run incluye todo lo que el manifiesto congela
        (hash, opciones completas de celdas y diagnósticos, ids por slot,
        canario, topes) y el JSON íntegro exportado verifica igual."""
        out = []
        qs_mod.plan(out.append)
        text = "\n".join(out)
        man = qs_mod._plan_manifest()
        self.assertIn(man["manifest_sha256"], text)
        self.assertIn(json.dumps(man["canary"], sort_keys=True), text)
        self.assertIn(str(man["calendar_base"]), text)
        for s in man["slots"]:
            self.assertIn(str(s["case_ids"]), text)
        for d in man["diag"]:
            self.assertIn(json.dumps(d["opts"], sort_keys=True), text)
            self.assertIn(str(d["case_ids"]), text)
        # el JSON íntegro del manifiesto aparece en la salida
        self.assertIn('"manifest_sha256"', text)
        self.assertIn('"p712_cases"', text)
        # y el fichero exportado es el manifiesto que verifica el ejecutor
        saved = json.loads(qs_mod._manifest_path().read_text())
        self.assertEqual(saved["manifest_sha256"],
                         man["manifest_sha256"])


# ------------------------------------------------------- correcciones R18

class TestR18HistoricalRef(TmpStore):
    """R18 §1 (sonda): la referencia histórica de REF_RUN que comparten
    off/typesafe y discrete queda congelada — en la evidencia inmutable
    de cada puerta y en el manifiesto del dry-run. Cambiarla invalida la
    puerta, la auditoría nunca produce un falso evaluable y el ejecutor
    se niega."""

    def _write_hist(self, n):
        """Referencia histórica respaldada por el almacén (el cargador
        real de j67, no un mock)."""
        ids = [c.id for c in load_phase("triage_es")[1]]
        store.save(qs_mod.REF_RUN, "triage_es",
                   {"meta": {}, "cases": {cid: {"usage":
                                              {"input_tokens": n}}
                                          for cid in ids}})

    def _drift_setup(self, cell, gid, run_kw=None):
        """Puerta aprobada con histórico de 100 tokens + run que midió 10;
        el histórico vigente baja después a 10."""
        key = qs_mod.cell_gate_key(cell)
        self._write_hist(100)
        hist100 = qs_mod.j67.load_token_ref()
        man_before = qs_mod._plan_manifest()
        qs_mod._manifest_path().write_text(json.dumps(man_before))
        _write_gate_archive(key, gid, hist=hist100,
                            offsets=({"triageadv": 0}
                                     if cell["mode"] == "discrete"
                                     else None))
        _write_run(cell["run"], "triage_es", hit=True, raw=True,
                   gate_id=gid, usage=10, **(run_kw or {}))
        return key, man_before

    def _assert_drift_rejected(self, cell, key, man_before):
        """Con 100 en la puerta y 10 vigentes: nada se vuelve evaluable,
        la puerta deja de valer y el manifiesto ya no verifica."""
        # sin falso evaluable NI antes ni después del cambio
        aud_before = qs_mod._audit_cell("T", cell)
        self.assertFalse(aud_before["evaluable"])
        self.assertEqual(len(aud_before["token_violations"]), 14)
        self._write_hist(10)
        aud_after = qs_mod._audit_cell("T", cell)
        self.assertFalse(aud_after["evaluable"])
        self.assertEqual(len(aud_after["token_violations"]), 14)
        # la puerta deja de valer: el histórico vigente (10) difiere del
        # que autorizó su gate_id (100)
        ctx = _ctx({"T": cell})
        self.assertFalse(qs_mod._cell_gate_ok(ctx, cell))
        # y el ejecutor se niega: el manifiesto congeló el histórico
        man_after = qs_mod._plan_manifest()
        self.assertNotEqual(man_before["manifest_sha256"],
                            man_after["manifest_sha256"])
        err, _ = qs_mod._verify_manifest()
        self.assertIsNotNone(err)

    def test_historico_100_a_10_off_typesafe(self):
        cell = _fake_cell(run="hist_drift_off")
        key, man_before = self._drift_setup(
            cell, "gate_qwen_prob_typesafe_off_d0@t~u")
        self._assert_drift_rejected(cell, key, man_before)

    def test_historico_100_a_10_discrete(self):
        """Discrete comparte la misma referencia histórica (sus offsets se
        miden sobre ella): el cambio también la invalida."""
        cell = _fake_cell(run="hist_drift_disc", mode="discrete")
        key, man_before = self._drift_setup(
            cell, "gate_qwen_disc_typesafe_off_d0@t~u",
            run_kw={"mode": "discrete"})
        self._assert_drift_rejected(cell, key, man_before)

    def test_historico_intacto_permite_ejecutar(self):
        """Con el histórico vigente idéntico al archivado por la puerta,
        la celda queda habilitada y se vigila con la referencia de la
        puerta."""
        cell = _fake_cell(run="hist_ok")
        key = qs_mod.cell_gate_key(cell)
        gid = f"gate_qwen_{key}@t~u"
        self._write_hist(10)
        _write_gate_archive(key, gid, hist=qs_mod.j67.load_token_ref())
        ctx = _ctx({"T": cell})
        self.assertTrue(qs_mod._cell_gate_ok(ctx, cell))
        self.assertEqual(ctx["hist"]["triage_es"]["T01_ebus_alergia"], 10)

    def test_puerta_sin_historico_archivado_no_vale(self):
        """Una puerta anterior al congelado (entry sin refs) ya no
        autoriza combos de referencia histórica: hay que repetirla."""
        cell = _fake_cell(run="hist_legacy")
        key = qs_mod.cell_gate_key(cell)
        self._write_hist(10)
        _write_gate_archive(key, f"gate_qwen_{key}@t~u")   # entry antiguo
        ctx = _ctx({"T": cell})
        self.assertFalse(qs_mod._cell_gate_ok(ctx, cell))


class TestR18HealthDeadline(TmpStore):
    """R18 §2 (sondas): el deadline de health limita el socket, el sleep
    y se comprueba antes de cada sonda — con ambos presupuestos."""

    class _TimeoutModel(_StubModel):
        def decide(self, *a):
            e = TimeoutError("timeout")
            e.diag = {"attempts": 1}
            raise e

    def _advance(self, clock, s):
        clock[0] += s

    def test_health_socket_acotado_al_remanente(self):
        """Sesión con 1 s restante: el socket de /health no puede pedir
        5 s — recibe como mucho el remanente y la espera no excede el
        tope de sesión."""
        clock = [0.0]
        opened = []

        def urlopen(url, timeout):
            opened.append(timeout)
            clock[0] += timeout
            raise TimeoutError("fake health timeout")

        cells = {"T": _fake_cell(run="h_sock")}
        ctx = _ctx(cells, model=self._TimeoutModel())
        ctx["st"]["elapsed_s"] = qs_mod.SESSION_CAP_S - 1
        ctx["elapsed_base"] = ctx["st"]["elapsed_s"]
        with mock.patch.object(qs_mod.urllib.request, "urlopen",
                               side_effect=urlopen):
            qs_mod._exec_slot(ctx, "T", "triage_es", False,
                              lambda: clock[0],
                              lambda s: self._advance(clock, s),
                              lambda *a, **k: None)
        self.assertTrue(opened)
        self.assertLessEqual(opened[0], 1.0)          # min(5, remanente)
        self.assertLessEqual(qs_mod._load_state()["elapsed_s"],
                             qs_mod.SESSION_CAP_S)

    def test_health_sleep_acotado_al_remanente(self):
        """Sesión con 1 s y sonda que falla al instante: el sleep tampoco
        puede dormir los 10 s del paso — queda acotado al remanente."""
        clock = [0.0]
        cells = {"T": _fake_cell(run="h_sleep")}
        ctx = _ctx(cells, model=self._TimeoutModel())
        ctx["st"]["elapsed_s"] = qs_mod.SESSION_CAP_S - 1
        ctx["elapsed_base"] = ctx["st"]["elapsed_s"]
        with mock.patch.object(qs_mod, "health_ok", return_value=False):
            qs_mod._exec_slot(ctx, "T", "triage_es", False,
                              lambda: clock[0],
                              lambda s: self._advance(clock, s),
                              lambda *a, **k: None)
        self.assertLessEqual(qs_mod._load_state()["elapsed_s"],
                             qs_mod.SESSION_CAP_S)

    def test_health_celda_agotada_con_sesion_disponible(self):
        """Variante de la sonda: celda al límite (0.5 s) con sesión
        disponible — la sonda se acota al remanente de celda y no
        excede ninguno de los dos topes."""
        clock = [0.0]
        opened = []

        def urlopen(url, timeout):
            opened.append(timeout)
            clock[0] += timeout
            raise TimeoutError("fake health timeout")

        cell = _fake_cell(run="h_cell", budget_s=600)
        ctx = _ctx({"T": cell}, model=self._TimeoutModel())
        ctx["st"]["cell_s"]["T"] = 599.5
        with mock.patch.object(qs_mod.urllib.request, "urlopen",
                               side_effect=urlopen):
            qs_mod._exec_slot(ctx, "T", "triage_es", False,
                              lambda: clock[0],
                              lambda s: self._advance(clock, s),
                              lambda *a, **k: None)
        self.assertTrue(opened)
        self.assertLessEqual(opened[0], 0.5)
        saved = qs_mod._load_state()
        self.assertLessEqual(saved["cell_s"]["T"], 600.0)
        self.assertLessEqual(saved["elapsed_s"], qs_mod.SESSION_CAP_S)
        # y se detiene la celda, no toda la sesión: la sesión tenía
        # presupuesto de sobra
        self.assertIsNone(ctx["session_stop"])
        self.assertIn("presupuesto de celda", ctx["cell_stop"]["T"])

    def test_health_sin_remanente_no_abre_sonda(self):
        """El remanente se comprueba ANTES de cada sonda: con deadline ya
        cumplido no se abre ni el socket."""
        clock = [0.0]
        opened = []

        def urlopen(url, timeout):
            opened.append(timeout)
            raise TimeoutError("fake")

        cells = {"T": _fake_cell(run="h_dead", budget_s=600)}
        ctx = _ctx(cells, model=self._TimeoutModel())
        ctx["st"]["elapsed_s"] = qs_mod.SESSION_CAP_S - 0.001
        ctx["elapsed_base"] = ctx["st"]["elapsed_s"]
        ctx["st"]["cell_s"]["T"] = 600.0     # celda justo en el tope
        with mock.patch.object(qs_mod.urllib.request, "urlopen",
                               side_effect=urlopen):
            qs_mod._exec_slot(ctx, "T", "triage_es", False,
                              lambda: clock[0],
                              lambda s: self._advance(clock, s),
                              lambda *a, **k: None)
        self.assertEqual(opened, [])


class TestR18TiempoInterrumpido(TmpStore):
    """R18 §3 (sonda): una petición que muere a media llamada no regala
    su tiempo — la marca temporal durable persistida antes de abrirla
    permite cargar lo consumido contra sesión y celda al reanudar."""

    def test_crash_en_decide_carga_el_tiempo_al_reanudar(self):
        clock = [0.0]

        class Interrupted(_StubModel):
            def decide(self, *a):
                clock[0] += 100
                raise KeyboardInterrupt("fake crash during request")

        cells = {"T": _fake_cell(run="elapsed_crash", budget_s=600)}
        ctx = _ctx(cells, model=Interrupted())
        qs_mod._save_state(ctx["st"])
        with mock.patch.object(qs_mod, "_wall", lambda: clock[0]):
            with self.assertRaises(KeyboardInterrupt):
                qs_mod._exec_slot(ctx, "T", "triage_es", False,
                                  lambda: clock[0], lambda s: None,
                                  lambda *a, **k: None)
            saved = qs_mod._load_state()
            # la reserva de peticiones sigue asentada y la marca durable
            # del tiempo pendiente está en disco
            self.assertEqual(saved["requests"], 3)
            self.assertEqual(saved["pending"]["case"], "T01_ebus_alergia")
            self.assertEqual(saved["pending"]["budget_key"], "T")
            # la reanudación concilia: los 100 s quedan consumidos contra
            # sesión y celda, no se recuperan
            st2 = qs_mod.session_begin("s1")
            self.assertGreaterEqual(st2["elapsed_s"], 100)
            self.assertGreaterEqual(st2["cell_s"]["T"], 100)
            self.assertIsNone(st2["pending"])
            self.assertEqual(st2["reconciled_pending"][-1]["charged_s"],
                             100)
            # y no se descuenta dos veces
            st3 = qs_mod.session_begin("s1")
            self.assertEqual(st3["elapsed_s"], st2["elapsed_s"])
            # al seguir el slot, el tiempo parte de lo conciliado
            ctx2 = _ctx(cells, model=_StubModel())
            ctx2["st"] = qs_mod._load_state()
            ctx2["t0"] = clock[0]
            ctx2["elapsed_base"] = st3["elapsed_s"]
            qs_mod._exec_slot(ctx2, "T", "triage_es", False,
                              lambda: clock[0], lambda s: None,
                              lambda *a, **k: None)
            final = qs_mod._load_state()
            self.assertGreaterEqual(final["elapsed_s"], 100)

    def test_crash_en_puerta_carga_el_tiempo_al_reanudar(self):
        """El mismo cierre dentro de una petición de puerta: la marca
        durable también está y el tiempo se carga a la sesión."""
        clock = [0.0]

        class Interrupted(_StubModel):
            def decide(self, *a):
                clock[0] += 100
                raise KeyboardInterrupt("fake crash during gate request")

        hist = {ph: {case.id: 310}
                for ph, case in qs_mod._gate_cases()}
        with mock.patch.object(qs_mod, "_wall", lambda: clock[0]):
            with self.assertRaises(KeyboardInterrupt):
                qs_mod.gate("prob_typesafe_off_d0", session="s1",
                            model_factory=lambda o: Interrupted(),
                            hist_ref=hist, printer=lambda *a: None)
            saved = qs_mod._load_state()
            self.assertIsNotNone(saved["pending"])
            st2 = qs_mod.session_begin("s1")
            self.assertGreaterEqual(st2["elapsed_s"], 100)
            self.assertIsNone(st2["pending"])

    def test_crash_tras_guardar_resultado_no_duplica_tiempo(self):
        """R19 (sonda): cierre en la ventana entre el store.save del
        resultado y la limpieza de pending — el caso ya contabilizado no
        se carga dos veces al reanudar: elapsed/cell quedan en 100, no
        200, y la conciliación es idempotente en la segunda reanudación."""
        clock = [0.0]
        run = "result_saved"

        class Model(_StubModel):
            def decide(self, *a):
                clock[0] += 100
                return super().decide(*a)

        cells = {"T": _fake_cell(run=run)}
        ctx = _ctx(cells, model=Model())
        qs_mod._save_state(ctx["st"])
        orig = store.save

        def save_then_crash(r, ph, doc):
            orig(r, ph, doc)
            if r == run:
                raise KeyboardInterrupt("crash after durable result, "
                                        "before pending cleared")

        with mock.patch.object(qs_mod, "_wall", lambda: clock[0]), \
             mock.patch.object(store, "save", side_effect=save_then_crash):
            with self.assertRaises(KeyboardInterrupt):
                qs_mod._exec_slot(ctx, "T", "triage_es", False,
                                  lambda: clock[0], lambda s: None,
                                  lambda *a, **k: None)
            before = qs_mod._load_state()
            # el caso quedó guardado y su duración ya consta en disco —
            # con pending todavía abierto
            self.assertEqual(before["elapsed_s"], 100)
            self.assertEqual(before["cell_s"]["T"], 100)
            self.assertEqual(len(store.load(run, "triage_es")["cases"]), 1)
            self.assertIsNotNone(before["pending"])
            resumed = qs_mod.session_begin("s1")
            again = qs_mod.session_begin("s1")
        # concilia solo lo no contabilizado: 100, no 200
        self.assertEqual(resumed["elapsed_s"], 100)
        self.assertEqual(resumed["cell_s"]["T"], 100)
        self.assertEqual(
            resumed["reconciled_pending"][-1]["charged_s"], 0)
        self.assertIsNone(resumed["pending"])
        # idempotente en una segunda reanudación
        self.assertEqual(again["elapsed_s"], 100)
        self.assertEqual(again["cell_s"]["T"], 100)


# -------------------------------------------------- Enmienda 2 / C15

def _cells_pair(budget, run_a="am_t0", run_b="am_t1"):
    """Dos celdas llamadas T0/T1 (el diff de la Enmienda 2 las toca por
    nombre) con el presupuesto dado — mismo combo off/typesafe."""
    return {"T0": _fake_cell(run=run_a, budget_s=budget),
            "T1": _fake_cell(run=run_b, budget_s=budget)}


class TestManifestTransition(TmpStore):
    """C15/Enmienda 2: transición autorizada de manifiesto — solo el diff
    de budget_s T0/T1 9000→12600; procedencia registrada en estado, diag
    y por caso; auditoría contra la cadena."""

    CAL = [("T0", "triage_es"), ("T1", "triage_es")]

    def _manifest(self, cells, cal=None):
        cal = self.CAL if cal is None else cal
        with mock.patch.object(qs_mod, "CELLS", cells), \
             mock.patch.object(qs_mod, "_calendar", lambda: cal), \
             mock.patch.object(qs_mod.j67, "load_token_ref",
                               _default_hist):
            return qs_mod._plan_manifest()

    def _env(self, cells, cal=None):
        cal = self.CAL if cal is None else cal
        patches = [
            mock.patch.object(qs_mod, "CELLS", cells),
            mock.patch.object(qs_mod, "_calendar", lambda: cal),
            mock.patch.object(qs_mod.j67, "load_token_ref",
                              _default_hist),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        key = qs_mod.cell_gate_key(cells["T0"])
        _write_gate_archive(key, "g@t", hist=_default_hist())

    def _amend_table(self, old, new):
        return {old["manifest_sha256"]: {
            "new_sha256": new["manifest_sha256"],
            "motivo": "enmienda de test", "fecha": "2026-10-06",
            "apply": qs_mod._amend_budget_t0t1}}

    def _run_kw(self, **kw):
        d = dict(session="s1", model_factory=lambda o: _StubModel(),
                 now=mock.Mock(return_value=0.0),
                 printer=lambda *a, **k: None)
        d.update(kw)
        return d

    def test_enmienda2_registrada_y_transformacion(self):
        """La tabla congelada declara el par real 428456d0→26bbda7c y la
        transformación solo toca budget_s de T0/T1 (cells y slots)."""
        am = qs_mod.MANIFEST_AMENDMENTS["428456d0e43b92eb"]
        self.assertEqual(am["new_sha256"], "26bbda7c05059d26")
        old = {"cells": {"T0": {"budget_s": 9000},
                         "T1": {"budget_s": 9000},
                         "F0": {"budget_s": 5400}},
               "slots": [{"cell": "T0", "budget_s": 9000},
                         {"cell": "T1", "budget_s": 9000},
                         {"cell": "F0", "budget_s": 5400}],
               "otro": {"x": 1}, "manifest_sha256": "428456d0e43b92eb"}
        out = am["apply"](old)
        self.assertEqual(out["cells"]["T0"]["budget_s"], 12600)
        self.assertEqual(out["cells"]["T1"]["budget_s"], 12600)
        self.assertEqual(out["cells"]["F0"]["budget_s"], 5400)
        self.assertEqual([s["budget_s"] for s in out["slots"]],
                         [12600, 12600, 5400])
        self.assertEqual(out["otro"], {"x": 1})
        # entrada que no es la esperada -> None (el diff no cuadra)
        self.assertIsNone(am["apply"]({"cells": {"T0": {"budget_s": 8000},
                                                "T1": {"budget_s": 9000}},
                                      "slots": []}))
        # y las constantes reales ya son las de la enmienda (210 min)
        self.assertEqual(qs_mod.CELLS["T0"]["budget_s"], 210 * 60)
        self.assertEqual(qs_mod.CELLS["T1"]["budget_s"], 210 * 60)

    def test_transicion_budget_reanuda_conserva_y_marca(self):
        """Reanudación real sobre un almacén temporal: casos guardados
        con el hash antiguo → continúa, conserva contadores/cell_s,
        aplica el nuevo budget y registra la cadena."""
        cells_old = _cells_pair(9000)
        cells_new = _cells_pair(12600)
        man_old = self._manifest(cells_old)
        man_new = self._manifest(cells_new)
        self.assertNotEqual(man_old["manifest_sha256"],
                            man_new["manifest_sha256"])
        # ejecución completa bajo el manifiesto antiguo
        self._env(cells_old)
        qs_mod._manifest_path().write_text(json.dumps(man_old))
        rc = qs_mod.run(**self._run_kw())
        self.assertEqual(rc, 0)
        doc = store.load("am_t0", "triage_es")
        self.assertEqual(doc["meta"]["diag"]["manifest_sha256"],
                         man_old["manifest_sha256"])
        self.assertEqual(len(doc["cases"]), 14)
        # un caso se reejecutará bajo el manifiesto nuevo
        cid = sorted(doc["cases"])[-1]
        del doc["cases"][cid]
        store.save("am_t0", "triage_es", doc)
        # celda por encima del tope ANTIGUO (9000): solo el nuevo
        # presupuesto (12600) le permite seguir
        st = qs_mod._load_state()
        st["cell_s"]["T0"] = 9100.0
        qs_mod._save_state(st)
        reqs = st["requests"]
        # archivo del manifiesto anterior + recongelo del nuevo
        old_file = self.tmp / "logs" / "manifiesto_anterior.json"
        old_file.write_text(json.dumps(man_old))
        qs_mod._manifest_path().write_text(json.dumps(man_new))
        with mock.patch.object(qs_mod, "CELLS", cells_new), \
             mock.patch.object(qs_mod, "MANIFEST_AMENDMENTS",
                               self._amend_table(man_old, man_new)):
            rc = qs_mod.run(**self._run_kw(
                resume=True, amend_manifest=str(old_file)))
        self.assertEqual(rc, 0)
        doc = store.load("am_t0", "triage_es")
        diag = doc["meta"]["diag"]
        self.assertEqual(diag["manifest_sha256"],
                         man_new["manifest_sha256"])
        am = diag["manifest_amendments"][0]
        self.assertEqual(am["old_sha256"], man_old["manifest_sha256"])
        self.assertEqual(am["new_sha256"], man_new["manifest_sha256"])
        self.assertIn("motivo", am)
        self.assertIn("fecha", am)
        # el caso reejecutado lleva el sha vigente; los antiguos
        # conservan el suyo propio (el eslabón anterior de la cadena)
        self.assertEqual(doc["cases"][cid]["manifest_sha256"],
                         man_new["manifest_sha256"])
        self.assertEqual(
            doc["cases"]["T01_ebus_alergia"]["manifest_sha256"],
            man_old["manifest_sha256"])
        # contadores conservados y nuevos consumos encima
        st = qs_mod._load_state()
        self.assertEqual(st["requests"], reqs + 1)
        self.assertEqual(st["manifest_amendments"][0]["old_sha256"],
                         man_old["manifest_sha256"])
        # el manifiesto anterior queda archivado, inmutable
        arch = (self.tmp / "logs" /
                f"qwen_manifest_{man_old['manifest_sha256']}.json")
        self.assertTrue(arch.exists())
        self.assertEqual(json.loads(arch.read_text())["manifest_sha256"],
                         man_old["manifest_sha256"])
        # la auditoría acepta la cadena: el doc mezcla casos bajo ambos
        # hashes autorizados (la tabla congelada sigue declarando la
        # enmienda — en producción la entrada es permanente)
        cell = _fake_cell(run="am_t0")
        _write_gate_archive(qs_mod.cell_gate_key(cell), "g@t",
                            hist=_default_hist())
        with mock.patch.object(qs_mod.j67, "load_token_ref",
                               _default_hist), \
             mock.patch.object(qs_mod, "MANIFEST_AMENDMENTS",
                               self._amend_table(man_old, man_new)):
            aud = qs_mod._audit_cell("T", cell)
        self.assertEqual(aud["manifest_bad"], [])
        self.assertTrue(aud["evaluable"], aud)

    def test_transicion_rechaza_otros_cambios(self):
        """El diff autorizado es exacto: otra diferencia en opts,
        manifiesto manipulado o sha ajeno a la cadena -> rechazo."""
        man_old = self._manifest(_cells_pair(9000))
        # misma enmienda pero además cambia la seed (opts distintas)
        cells_bad = _cells_pair(12600)
        cells_bad["T0"]["seed"] = 202
        man_bad = self._manifest(cells_bad)
        f = self.tmp / "logs" / "old.json"
        f.write_text(json.dumps(man_old))
        table = self._amend_table(man_old, man_bad)
        with mock.patch.object(qs_mod, "MANIFEST_AMENDMENTS", table):
            with self.assertRaises(SystemExit):
                qs_mod._resolve_amendment(str(f), man_bad)
        # manifiesto anterior manipulado: su sha declarado no cuadra
        bad = json.loads(json.dumps(man_old))
        bad["caps"]["requests"] = 4999
        f.write_text(json.dumps(bad))
        with mock.patch.object(qs_mod, "MANIFEST_AMENDMENTS", table):
            with self.assertRaises(SystemExit):
                qs_mod._resolve_amendment(str(f), man_bad)
        # sha anterior que no figura en la cadena autorizada
        man_x = self._manifest(_cells_pair(8000, run_a="x1", run_b="x2"))
        f.write_text(json.dumps(man_x))
        with mock.patch.object(qs_mod, "MANIFEST_AMENDMENTS", table):
            with self.assertRaises(SystemExit):
                qs_mod._resolve_amendment(str(f), man_bad)
        # y en el run completo: la transición rechazada no escribe nada
        cells_old = _cells_pair(9000)
        self._env(cells_old)
        man_old2 = self._manifest(cells_old)
        qs_mod._manifest_path().write_text(json.dumps(man_old2))
        self.assertEqual(qs_mod.run(**self._run_kw()), 0)
        qs_mod._manifest_path().write_text(json.dumps(man_bad))
        f.write_text(json.dumps(man_old2))
        table2 = self._amend_table(man_old2, man_bad)
        with mock.patch.object(qs_mod, "CELLS", cells_bad), \
             mock.patch.object(qs_mod, "MANIFEST_AMENDMENTS", table2):
            rc = qs_mod.run(**self._run_kw(resume=True,
                                         amend_manifest=str(f)))
        self.assertEqual(rc, 1)

    def test_resume_sin_enmienda_rechaza_como_antes(self):
        """Sin --amend-manifest la comprobación de hash no se relaja:
        el sha guardado antiguo sigue rechazando la reanudación."""
        cells_old = _cells_pair(9000)
        cells_new = _cells_pair(12600)
        man_old = self._manifest(cells_old)
        man_new = self._manifest(cells_new)
        self._env(cells_old)
        qs_mod._manifest_path().write_text(json.dumps(man_old))
        self.assertEqual(qs_mod.run(**self._run_kw()), 0)
        qs_mod._manifest_path().write_text(json.dumps(man_new))
        with mock.patch.object(qs_mod, "CELLS", cells_new), \
             mock.patch.object(qs_mod, "MANIFEST_AMENDMENTS",
                               self._amend_table(man_old, man_new)):
            with self.assertRaises(SystemExit):
                qs_mod.run(**self._run_kw(resume=True))

    def test_auditoria_rechaza_sha_ajeno_y_cadena_falsa(self):
        """La cadena se verifica eslabón a eslabón contra la tabla: un
        caso con sha ajeno o una enmienda registrada no autorizada hacen
        el run NO EVALUABLE."""
        cell = _fake_cell(run="chain_run")
        key = qs_mod.cell_gate_key(cell)
        gid = f"gate_qwen_{key}@t~u1"
        _write_gate_archive(key, gid, hist=_default_hist())
        _write_run("chain_run", "triage_es", hit=True, raw=True,
                   gate_id=gid)
        doc = store.load("chain_run", "triage_es")
        doc["meta"]["diag"]["manifest_sha256"] = "sha_nuevo"
        doc["meta"]["diag"]["manifest_amendments"] = [
            {"old_sha256": "sha_viejo", "new_sha256": "sha_nuevo"}]
        # caso escrito ya bajo el manifiesto nuevo
        cid = sorted(doc["cases"])[-1]
        doc["cases"][cid]["manifest_sha256"] = "sha_nuevo"
        store.save("chain_run", "triage_es", doc)
        table = {"sha_viejo": {"new_sha256": "sha_nuevo",
                               "motivo": "t", "fecha": "f",
                               "apply": lambda o: o}}
        with mock.patch.object(qs_mod, "MANIFEST_AMENDMENTS", table), \
             mock.patch.object(qs_mod.j67, "load_token_ref",
                               _default_hist):
            # ambos hashes de la cadena autorizan: antiguos sin marca
            # (origen = sha_viejo) y el nuevo por caso
            aud = qs_mod._audit_cell("T", cell)
            self.assertTrue(aud["evaluable"], aud)
            # un caso con sha ajeno a la cadena no está autorizado
            doc["cases"][cid]["manifest_sha256"] = "sha_ajeno"
            store.save("chain_run", "triage_es", doc)
            aud = qs_mod._audit_cell("T", cell)
            self.assertFalse(aud["evaluable"])
            self.assertEqual(aud["manifest_bad"], [f"triage_es/{cid}"])
            # y una enmienda registrada que no es la autorizada invalida
            # la fase entera
            doc["cases"][cid]["manifest_sha256"] = "sha_nuevo"
            doc["meta"]["diag"]["manifest_amendments"] = [
                {"old_sha256": "sha_falso",
                 "new_sha256": "sha_nuevo"}]
            store.save("chain_run", "triage_es", doc)
            aud = qs_mod._audit_cell("T", cell)
            self.assertFalse(aud["evaluable"])
            self.assertTrue(any("no autorizada" in m
                                for m in aud["manifest_bad"]))

    def test_celda_parada_por_tope_continua_con_enmienda(self):
        """T0 puede agotar el tope antiguo (9000 s) ANTES de aplicar la
        Enmienda 2: la reanudación con la transición autorizada y el
        nuevo budget (12600 s) continúa la celda — ejecuta los casos
        pendientes, no repite lo ya hecho y conserva el tiempo
        consumido."""
        cal = [("T0", "triage_es")]
        cells_old = _cells_pair(9000)
        cells_new = _cells_pair(12600)
        man_old = self._manifest(cells_old, cal)
        man_new = self._manifest(cells_new, cal)
        clock = [0.0]

        class Timed(_StubModel):
            def decide(self, *a):
                clock[0] += 800.0
                return super().decide(*a)

        self._env(cells_old, cal)
        qs_mod._manifest_path().write_text(json.dumps(man_old))
        rc = qs_mod.run(**self._run_kw(model_factory=lambda o: Timed(),
                                       now=lambda: clock[0]))
        self.assertEqual(rc, 2)              # parada por tope de celda
        doc = store.load("am_t0", "triage_es")
        self.assertEqual(len(doc["cases"]), 12)
        self.assertEqual(len(doc["meta"]["diag"]["stopped_cases"]), 2)
        st = qs_mod._load_state()
        self.assertGreaterEqual(st["cell_s"]["T0"], 9000.0)
        reqs = st["requests"]
        self.assertIsNone(st["pending"])
        # sin la enmienda, con el manifiesto y tope antiguos, la celda
        # sigue parada: no se abre ni un caso más
        rc = qs_mod.run(**self._run_kw(resume=True,
                                       model_factory=lambda o: Timed(),
                                       now=lambda: clock[0]))
        self.assertEqual(rc, 2)
        self.assertEqual(len(store.load("am_t0", "triage_es")["cases"]),
                         12)
        self.assertEqual(qs_mod._load_state()["requests"], reqs)
        # con la transición autorizada el nuevo budget aplica y la celda
        # continúa exactamente donde quedó
        old_file = self.tmp / "logs" / "manifiesto_anterior.json"
        old_file.write_text(json.dumps(man_old))
        qs_mod._manifest_path().write_text(json.dumps(man_new))
        with mock.patch.object(qs_mod, "CELLS", cells_new), \
             mock.patch.object(qs_mod, "MANIFEST_AMENDMENTS",
                               self._amend_table(man_old, man_new)):
            rc = qs_mod.run(**self._run_kw(
                resume=True, amend_manifest=str(old_file),
                model_factory=lambda o: Timed(), now=lambda: clock[0]))
        self.assertEqual(rc, 0)
        doc = store.load("am_t0", "triage_es")
        self.assertEqual(len(doc["cases"]), 14)
        nuevos = [c for c, r in doc["cases"].items()
                  if r.get("manifest_sha256")
                  == man_new["manifest_sha256"]]
        self.assertEqual(len(nuevos), 2)         # solo los pendientes
        st = qs_mod._load_state()
        self.assertEqual(st["requests"], reqs + 2)
        # el tiempo consumido se conserva y suma; nada se reinicia
        self.assertGreater(st["cell_s"]["T0"], 9000.0)
        self.assertLess(st["cell_s"]["T0"], 12600.0)
        self.assertEqual(doc["meta"]["diag"]["status"], "complete")

    def test_reanudacion_repetida_no_duplica_eslabon(self):
        """R26: tras una pausa, reanudar con el mismo --amend-manifest a
        otra hora NO añade un segundo eslabón old→new — la cadena se
        deduplica por identidad estable (conserva la primera `aplicada`)
        y la reanudación queda como evento aparte; la auditoría sigue
        evaluable y sigue rechazando eslabones ajenos."""
        cells_old = _cells_pair(9000)
        cells_new = _cells_pair(12600)
        man_old = self._manifest(cells_old)
        man_new = self._manifest(cells_new)
        self._env(cells_old)
        qs_mod._manifest_path().write_text(json.dumps(man_old))
        self.assertEqual(qs_mod.run(**self._run_kw()), 0)
        # dos casos pendientes en am_t0: la 1ª reanudación hará uno y la
        # pausa cortará antes del segundo; la 2ª lo completará
        doc = store.load("am_t0", "triage_es")
        ids = sorted(doc["cases"])[-2:]
        for cid in ids:
            del doc["cases"][cid]
        store.save("am_t0", "triage_es", doc)
        old_file = self.tmp / "logs" / "manifiesto_anterior.json"
        old_file.write_text(json.dumps(man_old))
        qs_mod._manifest_path().write_text(json.dumps(man_new))
        table = self._amend_table(man_old, man_new)

        class Pausa1(_StubModel):
            def decide(self, *a):
                out = super().decide(*a)
                if self.calls == 1:
                    qs_mod._pause_path().write_text("stop\n")
                return out

        # 1ª reanudación con enmienda (hora t-uno) → pausa limpia
        with mock.patch.object(qs_mod, "CELLS", cells_new), \
             mock.patch.object(qs_mod, "MANIFEST_AMENDMENTS", table), \
             mock.patch.object(qs_mod, "_iso", return_value="t-uno"):
            rc = qs_mod.run(**self._run_kw(
                resume=True, amend_manifest=str(old_file),
                model_factory=lambda o: Pausa1()))
        self.assertEqual(rc, 2)
        self.assertEqual(len(store.load("am_t0", "triage_es")["cases"]),
                         13)
        st = qs_mod._load_state()
        self.assertEqual(len(st["manifest_amendments"]), 1)
        self.assertEqual(st["manifest_amendments"][0]["aplicada"],
                         "t-uno")
        qs_mod._pause_path().unlink()
        # 2ª reanudación con el MISMO manifiesto anterior (hora t-dos)
        with mock.patch.object(qs_mod, "CELLS", cells_new), \
             mock.patch.object(qs_mod, "MANIFEST_AMENDMENTS", table), \
             mock.patch.object(qs_mod, "_iso", return_value="t-dos"):
            rc = qs_mod.run(**self._run_kw(
                resume=True, amend_manifest=str(old_file)))
        self.assertEqual(rc, 0)
        # la cadena sigue teniendo UN solo eslabón con la primera hora;
        # la segunda aplicación queda como evento de reanudación
        st = qs_mod._load_state()
        self.assertEqual(len(st["manifest_amendments"]), 1)
        self.assertEqual(st["manifest_amendments"][0]["aplicada"],
                         "t-uno")
        self.assertEqual(
            [e["aplicada"] for e in st["manifest_amendment_resumes"]],
            ["t-dos"])
        diag = store.load("am_t0", "triage_es")["meta"]["diag"]
        self.assertEqual(len(diag["manifest_amendments"]), 1)
        self.assertEqual(diag["manifest_amendments"][0]["aplicada"],
                         "t-uno")
        self.assertEqual(diag["manifest_amendment_resumes"][-1]
                         ["aplicada"], "t-dos")
        doc = store.load("am_t0", "triage_es")
        self.assertEqual(len(doc["cases"]), 14)
        # auditoría evaluable sobre la cadena deduplicada
        cell = _fake_cell(run="am_t0")
        with mock.patch.object(qs_mod.j67, "load_token_ref",
                               _default_hist), \
             mock.patch.object(qs_mod, "MANIFEST_AMENDMENTS", table):
            aud = qs_mod._audit_cell("T", cell)
            self.assertEqual(aud["manifest_bad"], [])
            self.assertTrue(aud["evaluable"], aud)
            # y un eslabón ajeno a la cadena sigue siendo rechazado
            doc["meta"]["diag"]["manifest_amendments"].append(
                {"old_sha256": "sha_ajeno",
                 "new_sha256": "sha_nuevo"})
            store.save("am_t0", "triage_es", doc)
            aud = qs_mod._audit_cell("T", cell)
        self.assertFalse(aud["evaluable"])
        self.assertTrue(aud["manifest_bad"])


class TestPausaCooperativa(TmpStore):
    """C15: results/logs/qwen_session.pause hace terminar el runner
    limpio tras el caso en curso — sin pending, lock liberado y
    reanudable."""

    def _env(self):
        cells = {"T": _fake_cell()}
        patches = [
            mock.patch.object(qs_mod, "CELLS", cells),
            mock.patch.object(qs_mod, "_calendar",
                              lambda: [("T", "triage_es")]),
            mock.patch.object(qs_mod.j67, "load_token_ref",
                              _default_hist),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        _write_gate_archive(qs_mod.cell_gate_key(cells["T"]), "g@t",
                            hist=_default_hist())
        qs_mod._manifest_path().write_text(
            json.dumps(qs_mod._plan_manifest(), ensure_ascii=False))

    def _run_kw(self, **kw):
        d = dict(session="s1", model_factory=lambda o: _StubModel(),
                 now=mock.Mock(return_value=0.0),
                 printer=lambda *a, **k: None)
        d.update(kw)
        return d

    def test_pausa_entre_casos_salida_limpia_y_reanuda(self):
        self._env()

        class Pausa(_StubModel):
            def decide(self, *a):
                out = super().decide(*a)
                if self.calls == 2:
                    qs_mod._pause_path().write_text("stop\n")
                return out

        rc = qs_mod.run(**self._run_kw(
            model_factory=lambda o: Pausa()))
        self.assertEqual(rc, 2)
        doc = store.load("t_run", "triage_es")
        self.assertEqual(len(doc["cases"]), 2)   # el caso en curso cerró
        st = qs_mod._load_state()
        self.assertIsNone(st["pending"])          # sin petición abierta
        self.assertEqual(st["requests"], 2)
        # lock liberado y estado/tiempos cerrados
        self.assertFalse(qs_mod._lock_path().exists())
        self.assertIn("elapsed_s", st)
        # la parada queda registrada: los casos no ejecutados figuran en
        # stopped_cases y el run queda "stopped", reanudable
        self.assertEqual(doc["meta"]["diag"]["status"], "stopped")
        self.assertEqual(len(doc["meta"]["diag"]["stopped_cases"]), 12)
        # al borrar el fichero la reanudación continúa donde quedó
        qs_mod._pause_path().unlink()
        rc = qs_mod.run(**self._run_kw(resume=True))
        self.assertEqual(rc, 0)
        doc = store.load("t_run", "triage_es")
        self.assertEqual(len(doc["cases"]), 14)

    def test_pausa_preexistente_no_abre_casos(self):
        self._env()
        qs_mod._pause_path().write_text("stop\n")
        model = _StubModel()
        rc = qs_mod.run(**self._run_kw(model_factory=lambda o: model))
        self.assertEqual(rc, 2)
        self.assertEqual(model.calls, 0)
        self.assertEqual(qs_mod._load_state()["requests"], 0)
        self.assertFalse(qs_mod._lock_path().exists())
        self.assertIsNone(store.load("t_run", "triage_es"))


# ------------------------------------------------- JEV-76 (factorial)

class TestJEV76Profile(TmpStore):
    """Perfil jev76 del supervisor (factorial discrete × thinking, 8
    celdas frescas): celdas, calendario, manifiesto, rutas y puertas
    propios — la sesión de jev68 queda intacta por defecto."""

    def setUp(self):
        super().setUp()
        qs_mod._set_profile("jev76")
        self.addCleanup(qs_mod._set_profile, "jev68")

    def test_rutas_propias_del_perfil(self):
        self.assertEqual(qs_mod._state_path().name,
                         "qwen_session_jev76.json")
        self.assertEqual(qs_mod._pause_path().name,
                         "qwen_session_jev76.pause")
        self.assertEqual(qs_mod._manifest_path().name,
                         "qwen_manifest_jev76.json")
        self.assertEqual(
            qs_mod._refs_path("disc_typesafe_on_d0").name,
            "qwen_refs_jev76_disc_typesafe_on_d0.json")
        self.assertEqual(qs_mod._gate_run("disc_typesafe_on_d0"),
                         "gate_qwen76_disc_typesafe_on_d0")
        # el lock es compartido entre perfiles a propósito: un solo
        # escritor sobre el mismo servidor
        self.assertEqual(qs_mod._lock_path().name, "qwen_session.lock")

    def test_estado_aislado_del_de_jev68(self):
        qs_mod.session_begin("s76")
        self.assertTrue(qs_mod._state_path().exists())
        self.assertFalse(
            (self.tmp / "logs" / "qwen_session.json").exists())
        qs_mod._set_profile("jev68")
        self.assertIsNone(qs_mod._load_state())   # jev68 no lo ve

    def test_perfil_desconocido_rechazado(self):
        with self.assertRaises(SystemExit):
            qs_mod._set_profile("jev99")

    def test_cells_tabla_jev76(self):
        self.assertEqual(len(qs_mod.CELLS), 8)
        self.assertEqual(qs_mod.CELLS["DT0"]["run"],
                         "llm_qwen38_27b_fp8_jev76_on_d0_disc")
        self.assertEqual(qs_mod.CELLS["DT1"]["run"],
                         "llm_qwen38_27b_fp8_jev76_on_d1_disc")
        self.assertEqual(qs_mod.CELLS["D1"]["run"],
                         "llm_qwen38_27b_fp8_jev76_off_d1_disc")
        self.assertTrue(qs_mod.CELLS["DT0"]["thinking"])
        self.assertTrue(qs_mod.CELLS["DT1"]["thinking"])
        self.assertFalse(qs_mod.CELLS["D0p"]["thinking"])
        # topes: off 90 min, on 210 min (como JEV-68 tras la Enmienda 2)
        for n in ("F0p", "F1p", "D0p", "D1"):
            self.assertEqual(qs_mod.CELLS[n]["budget_s"], 90 * 60, n)
        for n in ("T0p", "T1p", "DT0", "DT1"):
            self.assertEqual(qs_mod.CELLS[n]["budget_s"], 210 * 60, n)
        self.assertEqual(qs_mod.SESSION_CAP_S, 14 * 3600)
        self.assertEqual(qs_mod.REQUEST_CAP, 5000)

    def test_combos_jev76_ocho_sin_diagnosticos(self):
        combos = qs_mod.combos_needed()
        self.assertEqual(len(combos), 8)
        self.assertIn("disc_typesafe_on_d0", combos)
        self.assertIn("disc_typesafe_on_d1", combos)
        self.assertIn("disc_typesafe_off_d1", combos)
        self.assertNotIn("prob_sin_antinj_off_d0", combos)
        self.assertNotIn("prob_antinj_alt_off_d0", combos)
        self.assertEqual(qs_mod.cell_gate_key(qs_mod.CELLS["DT1"]),
                         "disc_typesafe_on_d1")

    def test_calendar_jev76_88_slots(self):
        slots = qs_mod._calendar()
        self.assertEqual(len(slots), 88)     # 11 fases × 8 celdas
        self.assertNotIn("S202", {c for c, _ in slots})
        base = qs_mod.CALENDAR_BASE
        self.assertEqual(len(base), 8)
        for i, ph in enumerate(qs_mod.PHASES_ALL):
            want = base[i % len(base):] + base[:i % len(base)]
            chunk = [c for c, p in slots if p == ph]
            self.assertEqual(chunk, want, ph)

    def test_manifiesto_jev76(self):
        man = qs_mod._plan_manifest()
        self.assertEqual(man["profile"], "jev76")
        self.assertEqual(len(man["slots"]), 88)
        self.assertEqual(len(man["cells"]), 8)
        self.assertEqual(man["diag"], [])
        self.assertEqual(man["p712_cases"], [])
        self.assertEqual(man["caps"]["session_s"], 14 * 3600)
        self.assertEqual(len(man["combos"]), 8)
        for k, c in man["combos"].items():
            if "_on_" in k:
                self.assertTrue(
                    c["token_ref"].startswith("qwen_refs_jev76_"), k)
            else:
                self.assertEqual(c["token_ref"], qs_mod.REF_RUN, k)

    def test_diag_rechazado_en_jev76(self):
        out = []
        self.assertEqual(qs_mod.diag(dry_run=True, printer=out.append), 1)
        self.assertTrue(any("P71.2" in linea for linea in out))

    def test_dry_run_plan_jev76(self):
        """El dry-run sin GPU emite las 8 puertas, los refs de los combos
        on, las 8 celdas con tope y los 88 slots — nada de JEV-68."""
        out = []
        qs_mod.plan(out.append)
        text = "\n".join(out)
        self.assertIn("perfil jev76", text)
        for key in qs_mod.combos_needed():
            self.assertIn(f"gate {key}", text)
        self.assertIn("--profile jev76", text)
        self.assertIn("qwen_refs_jev76_disc_typesafe_on_d0", text)
        self.assertIn("sin diagnósticos P71.2", text)
        self.assertIn("14 h", text)
        self.assertIn("llm_qwen38_27b_fp8_jev76_on_d0_disc", text)
        # el manifiesto exportado es el del perfil, no el de jev68
        self.assertTrue((self.tmp / "logs"
                         / "qwen_manifest_jev76.json").exists())
        self.assertFalse((self.tmp / "logs" / "qwen_manifest.json").exists())

    def test_jev68_intacto_tras_restaurar(self):
        """Salir del perfil deja celdas, calendario y rutas de jev68 tal
        cual — el mismo módulo sirve las dos sesiones sin mezclarlas."""
        qs_mod._set_profile("jev68")
        self.assertEqual(len(qs_mod.CELLS), 8)     # 7 baterías + S202
        self.assertIn("S202", qs_mod.CELLS)
        self.assertEqual(len(qs_mod._calendar()), 79)
        self.assertEqual(len(qs_mod.combos_needed()), 9)
        self.assertEqual(qs_mod._state_path().name, "qwen_session.json")
        self.assertEqual(qs_mod._manifest_path().name,
                         "qwen_manifest.json")
        self.assertEqual(qs_mod._gate_run("prob_typesafe_off_d0"),
                         "gate_qwen_prob_typesafe_off_d0")


class TestJEV76Gate(TmpStore):
    """La puerta de discrete+thinking aplica token_rule contra SU
    referencia tokenizer (±2), nunca offsets de off — corrección R30 de
    la asimetría de _gate_case_fails. D1/off mide sus propios offsets."""

    def setUp(self):
        super().setUp()
        self.qs = TRIAGE_QS
        self.combo_dt = {"mode": "discrete", "prompt": "typesafe",
                         "thinking": True, "order": "d0"}
        self.hist = {"triage_es": {"T01": 999}}

    def _fails_dt(self, rec, ref_on=None, offsets=None):
        req = rec["raw"][0]["request"]
        return qs_mod._gate_case_fails(
            self.combo_dt, "triage_es", "T01", rec, self.qs,
            _sha_of(req), self.hist, ref_on, {}, offsets if offsets is not None else {})

    def test_disc_on_usa_referencia_tokenizer(self):
        req = _mk_request(self.qs, mode="discrete", thinking=True)
        rec = _mk_rec(req, usage=300, reasoning="razonando")
        ref_on = {"triage_es": {"T01": 300}}
        offsets = {}
        fails = qs_mod._gate_case_fails(
            self.combo_dt, "triage_es", "T01", rec, self.qs,
            _sha_of(req), self.hist, ref_on, {}, offsets)
        self.assertEqual(fails, [])
        # DT no mide offsets ni los usa: su regla es la ref tokenizer
        self.assertEqual(offsets, {})
        # fuera de ±2 contra SU referencia -> violación, aunque el
        # histórico off (999) distaría mucho más
        rec2 = _mk_rec(req, usage=303, reasoning="razonando")
        fails2 = self._fails_dt(rec2, ref_on=ref_on)
        self.assertTrue(any("fuera de referencia" in f for f in fails2))
        rec3 = _mk_rec(req, usage=302, reasoning="razonando")
        self.assertEqual(self._fails_dt(rec3, ref_on=ref_on), [])

    def test_disc_on_sin_refs_falla(self):
        req = _mk_request(self.qs, mode="discrete", thinking=True)
        rec = _mk_rec(req, usage=300, reasoning="razonando")
        fails = self._fails_dt(rec)   # ref_on=None: referencias ausentes
        self.assertTrue(any("sin ref de tokens" in f for f in fails))

    def test_disc_on_exige_thinking_observado(self):
        """Declarar enable_thinking no basta en DT: el raw debe contener
        razonamiento observado (ni una salida vacía se etiqueta éxito)."""
        req = _mk_request(self.qs, mode="discrete", thinking=True)
        rec = _mk_rec(req, usage=300)     # sin reasoning_content
        fails = self._fails_dt(rec, ref_on={"triage_es": {"T01": 300}})
        self.assertTrue(any("thinking no efectivo" in f for f in fails))

    def test_disc_off_d1_offsets_propios(self):
        """D1 (discrete/off d1) lleva su puerta y sus offsets propios —
        no hereda los de D0: se miden contra el histórico aquí."""
        combo = {"mode": "discrete", "prompt": "typesafe",
                 "thinking": False, "order": "d1"}
        order = {"department": NAMED_ORDERS["department"]["d1"]}
        req = _mk_request(self.qs, order=order, mode="discrete")
        rec = _mk_rec(req, usage=250)
        offsets = {}
        fails = qs_mod._gate_case_fails(
            combo, "triage_es", "T01", rec, self.qs, _sha_of(req),
            {"triage_es": {"T01": 300}}, None, {}, offsets)
        self.assertEqual(fails, [])
        self.assertEqual(offsets[qs_mod.family("triage_es")], -50)


class TestJEV76Analysis(TmpStore):
    """Análisis factorial (H1/H2/I) del perfil jev76: 4 contrastes con
    IC98.75, interacción con bootstrap conjunto, NO EVALUABLE sin
    evidencia — todo offline con runs sintéticos de una fase."""

    def setUp(self):
        super().setUp()
        qs_mod._set_profile("jev76")
        self.addCleanup(qs_mod._set_profile, "jev68")

    def _cells_1ph(self):
        return {n: {**c, "phases": ["triage_es"]}
                for n, c in qs_mod.CELLS_76.items()}

    def _write_cell(self, cell, hit, usage=10):
        """Run con la evidencia completa que exige la auditoría: puerta
        archivada del perfil (refs tokenizer en `on`; histórico+offsets
        en `off`), raw con request/thinking y usage dentro de regla."""
        key = qs_mod.cell_gate_key(cell)
        combo = qs_mod.cell_combo(cell)
        order = {"department": NAMED_ORDERS["department"][cell["order"]]}
        gid = f"{qs_mod._gate_run(key)}@t~u"
        if qs_mod._needs_tokenizer_refs(combo):
            toks = {"triage_es": {c.id: usage
                                  for c in load_phase("triage_es")[1]}}
            rdoc = {"meta": {"combo": key}, "tokens": toks}
            qs_mod._refs_path(key).write_text(json.dumps(rdoc))
            _write_gate_archive(key, gid, refs_doc=rdoc)
        else:
            off = ({"triageadv": 0} if combo["mode"] == "discrete"
                   else None)
            _write_gate_archive(key, gid, hist=_default_hist(),
                                offsets=off)
        _write_run(cell["run"], "triage_es", hit=hit, raw=True,
                   gate_id=gid, usage=usage, mode=combo["mode"],
                   order=order, thinking=combo["thinking"],
                   reasoning="pienso" if combo["thinking"] else None)

    def test_joint_stat_boot_interaccion(self):
        """I=(DT−T)−(D−F) con los mismos clusters remuestreados en las
        cuatro celdas — nunca la resta de extremos de ICs por separado."""
        cells = self._cells_1ph()
        hits = {"F0p": False, "T0p": True, "D0p": False, "DT0": True,
                "F1p": False, "T1p": True, "D1": False, "DT1": True}
        with mock.patch.object(qs_mod, "CELLS", cells), \
             mock.patch.object(qs_mod.j67, "load_token_ref",
                               _default_hist):
            for n, c in cells.items():
                self._write_cell(c, hits[n])
            ib = qs_mod.joint_stat_boot(
                [cells[n]["run"] for n in ("F0p", "T0p", "D0p", "DT0")],
                lambda a: (a[3] - a[1]) - (a[2] - a[0]),
                iters=200, seed=1)
        self.assertIsNotNone(ib)
        # F/T y D/DT con el mismo contraste por pares -> I = 0 exacto
        self.assertAlmostEqual(ib["stat"], 0.0, places=6)
        self.assertLessEqual(ib["lo"], 0)
        self.assertGreaterEqual(ib["hi"], 0)
        # determinista por semilla
        with mock.patch.object(qs_mod, "CELLS", cells), \
             mock.patch.object(qs_mod.j67, "load_token_ref",
                               _default_hist):
            ib2 = qs_mod.joint_stat_boot(
                [cells[n]["run"] for n in ("F0p", "T0p", "D0p", "DT0")],
                lambda a: (a[3] - a[1]) - (a[2] - a[0]),
                iters=200, seed=1)
        self.assertEqual(ib["lo"], ib2["lo"])

    def test_analyze_factorial_clasifica(self):
        """Las cuatro celdas evaluables -> 4 contrastes con IC98.75:
        H1 confirmada en ambos órdenes (DT>>D) y H2 refutada (DT≈T);
        I por orden calculada como descriptiva."""
        cells = self._cells_1ph()
        hits = {"F0p": False, "T0p": True, "D0p": False, "DT0": True,
                "F1p": False, "T1p": True, "D1": False, "DT1": True}
        with mock.patch.object(qs_mod, "CELLS", cells), \
             mock.patch.object(qs_mod.j67, "load_token_ref",
                               _default_hist):
            for n, c in cells.items():
                self._write_cell(c, hits[n])
            rep = qs_mod.analyze(iters=100, seed=1,
                                 printer=lambda *a, **k: None)
        cls = rep["classification"]
        self.assertEqual(len(cls), 4)
        for k in ("H1 d0: DT−D >=+5", "H1 d1: DT−D >=+5"):
            self.assertTrue(cls[k].startswith("CONFIRMADA"), cls[k])
        for k in ("H2 d0: DT−T >=+5", "H2 d1: DT−T >=+5"):
            self.assertTrue(cls[k].startswith("REFUTADA"), cls[k])
        self.assertTrue(rep["runs"]["DT0"]["evaluable"],
                        rep["runs"]["DT0"])
        self.assertIsNotNone(rep["interaccion_d0"])
        self.assertAlmostEqual(rep["interaccion_d0"]["stat"], 0.0,
                               places=6)
        # Holm53 de los cuatro pares de los primarios
        self.assertEqual(sorted(rep["holm53"]),
                         ["D0p_vs_DT0", "D1_vs_DT1",
                          "T0p_vs_DT0", "T1p_vs_DT1"])

    def test_analyze_factorial_no_evaluable_sin_evidencia(self):
        """Sin runs completos autorizados no hay clasificación de
        cortesía: cada contraste queda NO EVALUABLE, nunca confirmado."""
        cells = self._cells_1ph()
        # solo las dos celdas de H1 d0, SIN puerta ni raw (no evaluables)
        with mock.patch.object(qs_mod, "CELLS", cells), \
             mock.patch.object(qs_mod.j67, "load_token_ref",
                               _default_hist):
            for n in ("D0p", "DT0"):
                _write_run(cells[n]["run"], "triage_es", hit=True)
            rep = qs_mod.analyze(iters=50, seed=1,
                                 printer=lambda *a, **k: None)
        for k in ("H1 d0: DT−D >=+5", "H1 d1: DT−D >=+5",
                  "H2 d0: DT−T >=+5", "H2 d1: DT−T >=+5"):
            self.assertTrue(rep["classification"][k].startswith(
                "NO EVALUABLE"), rep["classification"][k])
        self.assertIsNone(rep["interaccion_d0"])
        self.assertIsNone(rep["interaccion_d1"])

    def test_puerta_dt_dirige_al_perfil(self):
        """La evidencia de la puerta DT se archiva en gate_qwen76_*:
        _gate_entry_for la resuelve dentro del perfil, no en jev68."""
        key = "disc_typesafe_on_d0"
        gid = f"{qs_mod._gate_run(key)}@t~u9"
        rdoc = {"meta": {"combo": key},
                "tokens": {"triage_es": {"T01": 10}}}
        _write_gate_archive(key, gid, refs_doc=rdoc)
        e = qs_mod._gate_entry_for(key, gid)
        self.assertIsNotNone(e)
        toks, why = qs_mod._entry_refs(key, e)
        self.assertIsNotNone(toks, why)
        self.assertTrue(
            store.runs_in(f"gate_qwen76_{key}~u9"))
        self.assertFalse(
            store.runs_in(f"gate_qwen_{key}~u9"))


if __name__ == "__main__":
    unittest.main()


# --------------------------------------------------------------- JEV-77

class TestJEV77Profile(TmpStore):
    """Perfil jev77 (MedGemma/Gemma/Qwen en .80, medgemma_jev77): 18
    celdas en 5 checkpoints, calendario por bloques con rotación por
    fase, reloj WALL de 40 h con pausas, subsesión de 12 h, 12.000
    peticiones duras y refs tokenizer en TODOS los combos."""

    def setUp(self):
        super().setUp()
        qs_mod._set_profile("jev77")
        self.addCleanup(qs_mod._set_profile, "jev68")

    def test_rutas_propias_del_perfil(self):
        self.assertEqual(qs_mod._state_path().name,
                         "qwen_session_jev77.json")
        self.assertEqual(qs_mod._pause_path().name,
                         "qwen_session_jev77.pause")
        self.assertEqual(qs_mod._manifest_path().name,
                         "qwen_manifest_jev77.json")
        key = "disc_typesafe_off_d0_medgemma27b"
        self.assertEqual(qs_mod._refs_path(key).name,
                         f"qwen_refs_jev77_{key}.json")
        self.assertEqual(qs_mod._gate_run(key), f"gate_jev77_{key}")
        self.assertEqual(qs_mod._lock_path().name, "qwen_session.lock")

    def test_cells_18_con_checkpoint(self):
        self.assertEqual(len(qs_mod.CELLS), 18)
        self.assertEqual(
            qs_mod.CELLS["MD0"]["run"],
            "llm_medgemma_27b_it_bf16_jev77_d0_disc")
        self.assertEqual(
            qs_mod.CELLS["QD0p"]["run"],
            "llm_qwen38_27b_fp8_jev77_d0_disc")
        self.assertEqual(
            qs_mod.CELLS["G4D1"]["run"],
            "llm_gemma3_4b_it_bf16_jev77_d1_disc")
        # thinking: None en familia Gemma (sin flag), False en Qwen
        for n in ("MD0", "MP0", "MD1", "MP1", "GD0", "GP0", "GD1", "GP1",
                  "M4D0", "M4P0", "M4D1", "M4P1",
                  "G4D0", "G4P0", "G4D1", "G4P1"):
            self.assertIsNone(qs_mod.CELLS[n]["thinking"], n)
        self.assertFalse(qs_mod.CELLS["QD0p"]["thinking"])
        self.assertFalse(qs_mod.CELLS["QD1p"]["thinking"])
        # topes congelados en A4: 27B prob 150 / 27B disc 45 / Qwen 90 /
        # 4B 45 min (total 22 h) — regla común ≥30 % sobre 194×peor
        # latencia A3 + cobertura de prompts largos de papers32 (6,7k)
        for n in ("MP0", "MP1", "GP0", "GP1"):
            self.assertEqual(qs_mod.CELLS[n]["budget_s"], 150 * 60, n)
        for n in ("QD0p", "QD1p"):
            self.assertEqual(qs_mod.CELLS[n]["budget_s"], 90 * 60, n)
        for n in ("MD0", "MD1", "GD0", "GD1",
                  "M4D0", "M4P0", "M4D1", "M4P1",
                  "G4D0", "G4P0", "G4D1", "G4P1"):
            self.assertEqual(qs_mod.CELLS[n]["budget_s"], 45 * 60, n)
        self.assertEqual(
            sum(c["budget_s"] for c in qs_mod.CELLS.values()), 1320 * 60)
        # checkpoints con su identidad congelada del pre-registro
        self.assertEqual(qs_mod.CKPTS_77["medgemma27b"]["checkpoint"],
                         "google/medgemma-27b-it")
        self.assertEqual(qs_mod.CKPTS_77["gemma3_27b"]["sha"],
                         "005ad3404e59d6023443cb575daa05336842228a")
        self.assertEqual(qs_mod.SESSION_CAP_S, 40 * 3600)
        self.assertEqual(qs_mod.REQUEST_CAP, 12000)

    def test_claves_de_combo_con_checkpoint(self):
        combos = qs_mod.combos_needed()
        self.assertEqual(len(combos), 18)
        self.assertIn("disc_typesafe_off_d0_medgemma27b", combos)
        self.assertIn("prob_typesafe_off_d1_gemma3_4b", combos)
        combo = qs_mod.parse_gate_key("disc_typesafe_off_d0_medgemma27b")
        self.assertIsNone(combo["thinking"])
        self.assertEqual(combo["checkpoint"], "google/medgemma-27b-it")
        combo_q = qs_mod.parse_gate_key("disc_typesafe_off_d1_qwen38fp8")
        self.assertFalse(combo_q["thinking"])
        self.assertEqual(combo_q["checkpoint"], "Qwen/Qwen3.8-27B-FP8")
        # 'on' es ilegal en una familia sin flag thinking (Gemma)
        with self.assertRaises(SystemExit):
            qs_mod.parse_gate_key("disc_typesafe_on_d0_medgemma27b")
        # checkpoint desconocido
        with self.assertRaises(SystemExit):
            qs_mod.parse_gate_key("disc_typesafe_off_d0_llama9b")
        # los combos de jev77 todos llevan refs tokenizer propias
        for k in combos:
            self.assertTrue(qs_mod._needs_tokenizer_refs(
                qs_mod.parse_gate_key(k)), k)

    def test_extra_body_sin_flag_en_familia_gemma(self):
        # Gemma: la petición no declara enable_thinking en absoluto
        self.assertEqual(json.loads(qs_mod._extra_body(None, 101)),
                         {"temperature": 0, "seed": 101})
        # Qwen: declarado off, como en jev68
        self.assertEqual(
            json.loads(qs_mod._extra_body(False, 101))
            ["chat_template_kwargs"], {"enable_thinking": False})
        opts_g = qs_mod._combo_opts(
            qs_mod.parse_gate_key("prob_typesafe_off_d0_gemma3_27b"))
        self.assertEqual(opts_g["model"], "gemma-3-27b-it")
        self.assertEqual(opts_g["max_tokens"], "8192")
        opts_q = qs_mod._combo_opts(
            qs_mod.parse_gate_key("disc_typesafe_off_d0_qwen38fp8"))
        self.assertEqual(opts_q["model"], "qwen3.8-27b-sglang")
        self.assertEqual(opts_q["max_tokens"], "16384")

    def test_calendar_por_bloques_198_slots(self):
        slots = qs_mod._calendar()
        self.assertEqual(len(slots), 198)   # 18 celdas x 11 fases
        # orden de bloques = orden del manifiesto (§8.3)
        pos = 0
        for ck, names in qs_mod.BLOCKS_77:
            for i, ph in enumerate(qs_mod.PHASES_ALL):
                chunk = slots[pos:pos + len(names)]
                want = [names[(j + i) % len(names)]
                        for j in range(len(names))]
                self.assertEqual([c for c, _ in chunk], want,
                                 f"{ck}/{ph}")
                self.assertTrue(all(p == ph for _, p in chunk))
                pos += len(names)
        # la fase 0 del bloque MedGemma respeta el orden pre-registrado
        self.assertEqual([c for c, _ in slots[:4]],
                         ["MD0", "MP0", "MD1", "MP1"])

    def test_manifiesto_jev77(self):
        man = qs_mod._plan_manifest()
        self.assertEqual(man["profile"], "jev77")
        self.assertEqual(len(man["slots"]), 198)
        self.assertEqual(len(man["cells"]), 18)
        self.assertEqual(len(man["combos"]), 18)
        self.assertEqual(man["diag"], [])
        self.assertEqual(man["p712_cases"], [])
        self.assertEqual(man["caps"]["session_s"], 40 * 3600)
        self.assertEqual(man["caps"]["requests"], 12000)
        self.assertEqual(list(man["blocks"]),
                         [ck for ck, _ in qs_mod.BLOCKS_77])
        self.assertEqual(man["checkpoints"], qs_mod.CKPTS_77)
        for k, c in man["combos"].items():
            self.assertTrue(
                c["token_ref"].startswith("qwen_refs_jev77_"), k)
            self.assertTrue(c["gate"].startswith("gate_jev77_"), k)
        self.assertEqual(man["cells"]["MD0"]["opts"]["checkpoint"],
                         "google/medgemma-27b-it")

    def test_reloj_wall_40h_con_pausas(self):
        """jev77 corre con reloj WALL: nace en el primer session_begin
        (inicio A6, tras la preparación A3 registrada), sobrevive a
        --new-session y las pausas cuentan (§8.2)."""
        qs_mod.prep(requests=0, wall_s=0, printer=lambda *a: None)
        st = qs_mod.session_begin("s77")
        self.assertIsInstance(st.get("wall_t0"), float)
        wt0 = st["wall_t0"]
        # el reloj del tope lee wall - wall_t0, no el acumulado
        e = qs_mod._sess_elapsed(st, st["elapsed_s"], t0=0.0,
                                 now=lambda: 0.0)
        self.assertAlmostEqual(e, qs_mod._wall() - wt0, places=1)
        # --new-session conserva el reloj (los reinicios cuentan)
        st2 = qs_mod.session_begin("s77b", new_session=True)
        self.assertEqual(st2["wall_t0"], wt0)
        # en jev68/jev76 el reloj es el acumulado del supervisor
        qs_mod._set_profile("jev68")
        e68 = qs_mod._sess_elapsed({"elapsed_s": 0.0}, 5.0, t0=0.0,
                                   now=lambda: 7.0)
        self.assertEqual(e68, 5.0 + 7.0)

    def test_load_hist_tolerante_sin_historico(self):
        """jev77 no usa la referencia histórica de JEV-68: si el run
        REF_RUN no existe no tumba la sesión (todos sus combos llevan
        refs propias). En jev68 sigue siendo obligatoria."""
        with mock.patch.object(qs_mod.j67, "load_token_ref",
                               side_effect=SystemExit("sin ref")):
            self.assertEqual(qs_mod._load_hist(), {})
            qs_mod._set_profile("jev68")
            with self.assertRaises(SystemExit):
                qs_mod._load_hist()

    def test_subsesion_12h_en_exec_slot(self):
        """El tope de subsesión continua (12 h, §8.2) detiene el slot
        aunque quede presupuesto wall de sesión. La subsesión es
        DURABLE: se simula una instancia cargada hace 13 h (sub_t0 en
        el pasado), no una invocación larga (R36 §2)."""
        qs_mod.prep(requests=0, wall_s=0, printer=lambda *a: None)
        st = qs_mod.session_begin("s77")
        st["sub_t0"] = qs_mod._wall() - 13 * 3600
        qs_mod._save_state(st)
        cell = {**qs_mod.CELLS["MD0"], "phases": ["triage_es"]}
        ctx = _ctx({"MD0": cell}, st=st)
        ctx["t0"] = 0.0
        qs_mod._exec_slot(ctx, "MD0", "triage_es", False,
                          mock.Mock(return_value=0.0),
                          lambda s: None, lambda *a, **k: None)
        self.assertIn("subsesión", ctx["session_stop"])
        # en jev68 no hay subsesión: un salto parecido solo agota los
        # 10 h de sesión acumulada, con su mensaje habitual
        qs_mod._set_profile("jev68")
        st68 = {"session": "s1", "started": "x", "elapsed_s": 0.0,
                "requests": 0, "cell_s": {}, "retried": {},
                "sessions": ["s1"]}
        cell68 = _fake_cell(budget_s=20 * 3600)
        ctx68 = _ctx({"T": cell68}, st=st68)
        qs_mod._exec_slot(ctx68, "T", "triage_es", False,
                          mock.Mock(return_value=11 * 3600),
                          lambda s: None, lambda *a, **k: None)
        self.assertIn("tope de sesión", ctx68["session_stop"])
        self.assertNotIn("subsesión", ctx68["session_stop"])

    def test_diag_rechazado_en_jev77(self):
        out = []
        self.assertEqual(qs_mod.diag(dry_run=True, printer=out.append), 1)
        self.assertTrue(any("P71.2" in linea for linea in out))

    def test_dry_run_plan_jev77(self):
        """El dry-run emite las 18 puertas con checkpoint, los bloques,
        las refs propias y los topes de 40 h / 12.000 — sin tocar nada."""
        out = []
        qs_mod.plan(out.append)
        text = "\n".join(out)
        self.assertIn("perfil jev77", text)
        for key in qs_mod.combos_needed():
            self.assertIn(f"gate {key}", text)
        self.assertIn("--profile jev77", text)
        self.assertIn("bloque medgemma27b", text)
        self.assertIn("qwen_refs_jev77_disc_typesafe_off_d0_medgemma27b",
                      text)
        self.assertIn("sin diagnósticos P71.2", text)
        self.assertIn("40 h", text)
        self.assertIn("12000 peticiones", text)
        self.assertTrue((self.tmp / "logs"
                         / "qwen_manifest_jev77.json").exists())
        self.assertFalse(
            (self.tmp / "logs" / "qwen_manifest.json").exists())

    def test_jev68_y_jev76_intactos_tras_restaurar(self):
        qs_mod._set_profile("jev68")
        self.assertEqual(len(qs_mod.CELLS), 8)
        self.assertEqual(len(qs_mod._calendar()), 79)
        self.assertEqual(len(qs_mod.combos_needed()), 9)
        self.assertEqual(qs_mod._state_path().name, "qwen_session.json")
        qs_mod._set_profile("jev76")
        self.assertEqual(len(qs_mod.CELLS), 8)
        self.assertEqual(len(qs_mod._calendar()), 88)
        self.assertEqual(qs_mod._manifest_path().name,
                         "qwen_manifest_jev76.json")


class TestJEV77Gate(TmpStore):
    """Puertas jev77 (§7): visible/blind por combo, thinking=None en
    Gemma (nunca se declara la flag; el razonamiento emergente se
    registra, no bloquea), Qwen off declarado y observado, sha ciego
    propio y margen visible−ciego por familia."""

    def setUp(self):
        super().setUp()
        qs_mod._set_profile("jev77")
        self.addCleanup(qs_mod._set_profile, "jev68")
        self.qs = TRIAGE_QS
        self.combo_g = qs_mod.parse_gate_key(
            "prob_typesafe_off_d0_gemma3_27b")     # thinking None
        self.combo_q = qs_mod.parse_gate_key(
            "disc_typesafe_off_d0_qwen38fp8")      # thinking False

    def test_thinking_none_no_declara_ni_exige_observado(self):
        req = _mk_request(self.qs, thinking=None)
        rec = _mk_rec(req, usage=10)
        fails = qs_mod._gate_case_fails(
            self.combo_g, "triage_es", "T01", rec, self.qs,
            _sha_of(req), {}, {"triage_es": {"T01": 10}}, {}, {})
        self.assertEqual(fails, [])
        # el razonamiento emergente NO bloquea en la familia Gemma
        rec2 = _mk_rec(req, usage=10, reasoning="razonando")
        fails2 = qs_mod._gate_case_fails(
            self.combo_g, "triage_es", "T01", rec2, self.qs,
            _sha_of(req), {}, {"triage_es": {"T01": 10}}, {}, {})
        self.assertEqual(fails2, [])
        # pero declarar la flag en un combo sin modo thinking sí es
        # violación
        req3 = _mk_request(self.qs, thinking=True)
        rec3 = _mk_rec(req3, usage=10, reasoning="razonando")
        fails3 = qs_mod._gate_case_fails(
            self.combo_g, "triage_es", "T01", rec3, self.qs,
            _sha_of(req3), {}, {"triage_es": {"T01": 10}}, {}, {})
        self.assertTrue(any("sin modo thinking" in f for f in fails3))

    def test_qwen_off_declarado_y_observado(self):
        """En Qwen el off tiene que estar declarado Y observado: si el
        raw muestra razonamiento aunque se declaró off, falla."""
        order = {"department": NAMED_ORDERS["department"]["d0"]}
        req = _mk_request(self.qs, order=order, thinking=False,
                          mode="discrete")
        rec = _mk_rec(req, usage=10)
        fails = qs_mod._gate_case_fails(
            self.combo_q, "triage_es", "T01", rec, self.qs,
            _sha_of(req), {}, {"triage_es": {"T01": 10}}, {}, {})
        self.assertEqual(fails, [])
        rec2 = _mk_rec(req, usage=10, reasoning="pienso")
        fails2 = qs_mod._gate_case_fails(
            self.combo_q, "triage_es", "T01", rec2, self.qs,
            _sha_of(req), {}, {"triage_es": {"T01": 10}}, {}, {})
        self.assertTrue(any("thinking no efectivo" in f
                            for f in fails2))

    def test_discrete_off_usa_refs_propias_en_jev77(self):
        """Discrete+off de jev77 va contra SU referencia tokenizer (±2),
        nunca contra offsets del histórico — a diferencia de jev68/76."""
        self.assertTrue(qs_mod._needs_tokenizer_refs(self.combo_q))
        order = {"department": NAMED_ORDERS["department"]["d0"]}
        req = _mk_request(self.qs, order=order, thinking=False,
                          mode="discrete")
        rec = _mk_rec(req, usage=300)
        ref = {"triage_es": {"T01": 300}}
        offsets = {}
        fails = qs_mod._gate_case_fails(
            self.combo_q, "triage_es", "T01", rec, self.qs,
            _sha_of(req), {"triage_es": {"T01": 999}}, ref, {}, offsets)
        self.assertEqual(fails, [])
        self.assertEqual(offsets, {})      # no se miden offsets
        rec2 = _mk_rec(req, usage=303)
        fails2 = qs_mod._gate_case_fails(
            self.combo_q, "triage_es", "T01", rec2, self.qs,
            _sha_of(req), {"triage_es": {"T01": 999}}, ref, {}, {})
        self.assertTrue(any("fuera de referencia" in f for f in fails2))

    def test_blind_sha_propio(self):
        """§7.3 sonda 4: el prompt ciego lleva sha precomputado propio —
        distinto del visible — y debe igualar el observado."""
        req_b = _mk_request(self.qs, inject=False, thinking=None)
        rec_b = _mk_rec(req_b, usage=5)
        sha_b = _sha_of(req_b)
        fails, t = qs_mod._blind_fails(self.combo_g, "triage_es/A01",
                                       rec_b, self.qs, exp_sha=sha_b)
        self.assertEqual(fails, [])
        self.assertEqual(t, 5)
        fails2, _ = qs_mod._blind_fails(self.combo_g, "triage_es/A01",
                                        rec_b, self.qs,
                                        exp_sha="deadbeefcafe")
        self.assertTrue(any("sha system" in f for f in fails2))
        # el sha ciego difiere del visible (son prompts distintos)
        req_v = _mk_request(self.qs, inject=True, thinking=None)
        self.assertNotEqual(_sha_of(req_v), sha_b)

    def test_gate_completo_combo_gemma(self):
        """Puerta completa de un combo Gemma: 3 visibles + ciego +
        canario, evidencia en gate_jev77_* y wall_t0 en el estado.
        El primer arranque exige la preparación A3 registrada (R36)."""
        qs_mod.prep(requests=10, wall_s=60, printer=lambda *a: None)
        key = "prob_typesafe_off_d0_gemma3_27b"
        toks = {}
        for ph, c in qs_mod._gate_cases():
            toks.setdefault(ph, {})[c.id] = 640
        rdoc = {"meta": {"combo": key}, "tokens": toks}
        qs_mod._refs_path(key).write_text(json.dumps(rdoc))

        def factory(opts):
            inj = opts["inject_schema_in_prompt"] == "true"

            def payload(state, questions):
                if qs_mod.CANARY_QID in questions:
                    p = 0.9 if inj else 0.0
                    return {qs_mod.CANARY_QID: {
                        "ruta_admin": 1 - p, qs_mod.CANARY_LABEL: p,
                        "ruta_clinica": 0.0}}
                return ANSWERS

            return _StubModel(payload=payload, usage=640 if inj else 10,
                              inject=inj, thinking=None)

        ok, det = qs_mod.gate(key, session="s77", model_factory=factory,
                              printer=lambda *a: None)
        self.assertTrue(ok, det["fails"])
        self.assertIn("gate_jev77_", det["gate_id"])
        self.assertEqual(qs_mod._load_state()["session"], "s77")
        self.assertIsInstance(qs_mod._load_state()["wall_t0"], float)
        self.assertTrue(det["canary"]["ejecutado"])

    def test_enmienda1_jev77_ws_args(self):
        """Enmienda 1 (incidente de la puerta ciega 7-oct): el flag de
        gramática JSON compacta entra en los 5 checkpoints y SOLO en
        ellos — apply(viejo) reproduce el vigente, la entrada real está
        en la tabla autorizada y el archivo anterior se archiva."""
        flag = "--constrained-json-disable-any-whitespace"
        man_new = qs_mod._plan_manifest()
        # reconstruye el manifiesto anterior (sin el flag, sha propio)
        old = copy.deepcopy(man_new)
        for spec in old["checkpoints"].values():
            spec["args"] = [a for a in spec["args"] if a != flag]
        old["manifest_sha256"] = qs_mod._manifest_content_sha(old)
        self.assertEqual(len(old["checkpoints"]), 5)
        out = qs_mod._amend_jev77_ws_args(old)
        strip = lambda d: {k: v for k, v in d.items()
                           if k != "manifest_sha256"}
        self.assertEqual(strip(out), strip(man_new))
        self.assertTrue(all(flag in v["args"]
                            for v in out["checkpoints"].values()))
        # entrada que no es la esperada -> None (ya enmendada o rota)
        self.assertIsNone(qs_mod._amend_jev77_ws_args(man_new))
        self.assertIsNone(qs_mod._amend_jev77_ws_args({}))
        # resolución completa con la tabla parcheada a este par:
        # verifica, archiva el anterior y devuelve el eslabón
        f = self.tmp / "logs" / "old77.json"
        f.write_text(json.dumps(old))
        table = {old["manifest_sha256"]: {
            "new_sha256": man_new["manifest_sha256"], "motivo": "e1",
            "fecha": "2026-10-07",
            "apply": qs_mod._amend_jev77_ws_args}}
        with mock.patch.object(qs_mod, "MANIFEST_AMENDMENTS", table):
            am = qs_mod._resolve_amendment(str(f), man_new)
        self.assertEqual(am["old_sha256"], old["manifest_sha256"])
        self.assertEqual(am["new_sha256"], man_new["manifest_sha256"])
        arch = (self.tmp / "logs" /
                f"qwen_manifest_jev77_{old['manifest_sha256']}.json")
        self.assertTrue(arch.exists())
        # la tabla REAL enlaza el sha del encargo previo al flag
        real = qs_mod.MANIFEST_AMENDMENTS["008c1cdd499b6f92"]
        self.assertIs(real["apply"], qs_mod._amend_jev77_ws_args)
        self.assertIn("constrained-json", real["motivo"])

    def test_margen_ciego_por_familia(self):
        """El margen visible−ciego es el A01_MARGIN del combo congelado
        en A4: medido por tokenización (render visible−ciego de
        adv1/A01) menos 64 tokens de holgura — familia Gemma 304, Qwen
        292 (medgemma_jev77.md §A3/A4)."""
        self.assertEqual(self.combo_g["a01_margin"], 304)
        self.assertEqual(self.combo_q["a01_margin"], 292)


class TestJEV77Analysis(TmpStore):
    """Análisis jev77 (§6): H1/H2 confirmatorios en d0 con IC97.5,
    descriptivos IC95, subgrupos (department/papers/adv), Holm53 en diez
    familias y cascada aparte — offline con runs sintéticos."""

    def setUp(self):
        super().setUp()
        qs_mod._set_profile("jev77")
        self.addCleanup(qs_mod._set_profile, "jev68")

    def _cells_1ph(self):
        return {n: {**c, "phases": ["triage_es"]}
                for n, c in qs_mod.CELLS_77.items()}

    def _write_cell(self, cell, hit, usage=10):
        """Run con la evidencia completa que exige jev77: refs tokenizer
        propias por combo (todas), puerta archivada del perfil, raw con
        request (sin flag thinking en Gemma) y usage dentro de regla."""
        key = qs_mod.cell_gate_key(cell)
        combo = qs_mod.cell_combo(cell)
        order = {"department": NAMED_ORDERS["department"][cell["order"]]}
        gid = f"{qs_mod._gate_run(key)}@t~u"
        toks = {"triage_es": {c.id: usage
                              for c in load_phase("triage_es")[1]}}
        rdoc = {"meta": {"combo": key}, "tokens": toks}
        qs_mod._refs_path(key).write_text(json.dumps(rdoc))
        _write_gate_archive(key, gid, refs_doc=rdoc)
        _write_run(cell["run"], "triage_es", hit=hit, raw=True,
                   gate_id=gid, usage=usage, mode=combo["mode"],
                   order=order, thinking=combo["thinking"])

    def test_analyze_medgemma_clasifica(self):
        """M gana a G en discreto d0 (H1 ≥+5) y empata con Q (H2 ≥−5 de
        no inferioridad): ambas CONFIRMADAS con IC97,5."""
        cells = self._cells_1ph()
        with mock.patch.object(qs_mod, "CELLS", cells), \
             mock.patch.object(qs_mod.j67, "load_token_ref",
                               _default_hist):
            for n, c in cells.items():
                self._write_cell(c, hit=(n != "GD0"))
            rep = qs_mod.analyze(iters=100, seed=1,
                                 printer=lambda *a, **k: None)
        cls = rep["classification"]
        self.assertTrue(rep["runs"]["MD0"]["evaluable"],
                        rep["runs"]["MD0"])
        self.assertTrue(cls["H1: M-D0−G-D0 ≥+5"].startswith(
            "CONFIRMADA"), cls)
        self.assertTrue(
            cls["H2: M-D0−Q-D0′ ≥−5 (no inferioridad)"].startswith(
                "CONFIRMADA"), cls)
        self.assertEqual(rep["profile"], "jev77")
        # Holm53: las diez familias pre-registradas, ninguna confirmatoria
        self.assertEqual(len(rep["holm53"]), 10)
        self.assertIn("MD0_vs_GD0", rep["holm53"])
        self.assertIn("M4P1_vs_G4P1", rep["holm53"])
        # descriptivos: deltas IC95 + subgrupos (department computable
        # con una fase; papers32/adv no presentes -> None)
        deltas = rep["descriptivos"]["deltas"]
        self.assertEqual(len(deltas), 8)
        self.assertIsNotNone(deltas["prob_d0"])
        subs = rep["descriptivos"]["subgrupos"]
        self.assertIsNotNone(subs["M_G"]["department"])
        self.assertIsNone(subs["M_G"]["papers32"])
        self.assertNotIn("cascada", rep["descriptivos"])

    def test_analyze_medgemma_h2_refutada(self):
        """H2 = no inferioridad M−Q ≥ −5: si Q-D0′ gana holgado a M-D0
        el IC entero cae bajo −5 y la hipótesis queda REFUTADA."""
        cells = self._cells_1ph()
        with mock.patch.object(qs_mod, "CELLS", cells), \
             mock.patch.object(qs_mod.j67, "load_token_ref",
                               _default_hist):
            for n, c in cells.items():
                # M-D0 falla todo; Q-D0′ y el resto aciertan
                self._write_cell(c, hit=(n != "MD0"))
            rep = qs_mod.analyze(iters=100, seed=1,
                                 printer=lambda *a, **k: None)
        cls = rep["classification"]
        self.assertTrue(
            cls["H2: M-D0−Q-D0′ ≥−5 (no inferioridad)"].startswith(
                "REFUTADA"), cls)
        self.assertTrue(cls["H1: M-D0−G-D0 ≥+5"].startswith(
            "REFUTADA"), cls)     # M−G = −100

    def test_audit_cell_detecta_estado_alterado(self):
        """Sonda R38 §4: la auditoría de evaluabilidad pasa el estado
        del caso al check de cliente — un raw con el payload <document>
        sustituido queda NO EVALUABLE igual que en puerta/run."""
        cells = self._cells_1ph()
        cell = cells["MD0"]
        self._write_cell(cell, hit=True)
        with mock.patch.object(qs_mod, "CELLS", cells), \
             mock.patch.object(qs_mod.j67, "load_token_ref",
                               _default_hist):
            before = qs_mod._audit_cell("MD0", cell)
            doc = store.load(cell["run"], "triage_es")
            first = next(iter(doc["cases"].values()))
            first["raw"][0]["request"]["messages"][1]["content"] = (
                "ESTADO SUSTITUIDO")
            store.save(cell["run"], "triage_es", doc)
            after = qs_mod._audit_cell("MD0", cell)
        self.assertTrue(before["evaluable"], before)
        self.assertFalse(after["evaluable"], after)
        self.assertTrue(any("estado" in v
                            for v in after["client_violations"]),
                        after["client_violations"])

    def test_analyze_medgemma_no_evaluable(self):
        """Sin puertas ni raw no hay clasificación de cortesía."""
        cells = self._cells_1ph()
        with mock.patch.object(qs_mod, "CELLS", cells), \
             mock.patch.object(qs_mod.j67, "load_token_ref",
                               _default_hist):
            for n in ("MD0", "GD0"):
                _write_run(cells[n]["run"], "triage_es", hit=True)
            rep = qs_mod.analyze(iters=50, seed=1,
                                 printer=lambda *a, **k: None)
        for k in rep["classification"]:
            self.assertTrue(rep["classification"][k].startswith(
                "NO EVALUABLE"), rep["classification"][k])

    def test_subset_delta_pregunta_unica(self):
        """Subgrupo department: delta de puntos medios solo de esa
        pregunta, pareado por clusters, descriptivo (sin baseline)."""
        ra, rb = "sub_a", "sub_b"
        qs, cases = load_phase("triage_es")
        for run, hit in ((ra, True), (rb, False)):
            recs = {}
            for c in cases:
                a = _answers_hit(qs, c.gt) if hit else _answers_miss(
                    qs, c.gt)
                recs[c.id] = {"answers": a}
            store.save(run, "triage_es", {"meta": {}, "cases": recs})
        d = qs_mod.subset_delta(ra, rb, ["triage_es"], qid="department",
                                iters=50, seed=1)
        self.assertIsNotNone(d)
        self.assertEqual(d["qid"], "department")
        self.assertLess(d["delta"], 0)    # rb falla todo -> B−A < 0
        self.assertGreaterEqual(d["hi"], d["delta"])


# --------------------------------------------------- JEV-77: correcciones R36

class TestJEV77Prep(TmpStore):
    """R36 §3: la preparación A3 tiene reloj y cupo propios (4 h / 150
    peticiones locales que CUENTAN en las 12.000 duras pero no en las
    40 h), se exige antes del primer arranque A6 y queda cerrada tras él."""

    def setUp(self):
        super().setUp()
        qs_mod._set_profile("jev77")
        self.addCleanup(qs_mod._set_profile, "jev68")

    def test_a3_exigida_antes_de_a6(self):
        """Sin registro A3 el primer session_begin se rechaza (sonda R36:
        el reloj de 40 h no puede arrancar sin que A3 esté contabilizada)."""
        with self.assertRaises(SystemExit):
            qs_mod.session_begin("s0")
        qs_mod.prep(requests=5, wall_s=30, printer=lambda *a: None)
        st = qs_mod.session_begin("s0")
        self.assertIsInstance(st["wall_t0"], float)

    def test_a3_topes_y_cuenta_en_12000(self):
        """150 peticiones y 4 h son el tope; el gasto de A3 cuenta en las
        12.000 duras (no en las 40 h — no hay wall_t0 aún)."""
        out = []
        self.assertEqual(qs_mod.prep(requests=100, wall_s=3600,
                                     printer=out.append), 0)
        self.assertEqual(qs_mod.prep(requests=60, wall_s=0,
                                     printer=out.append), 1)   # 100+60>150
        self.assertEqual(qs_mod.prep(requests=50, wall_s=4 * 3600,
                                     printer=out.append), 1)   # 1+4 h>4 h
        self.assertEqual(qs_mod.prep(requests=50, wall_s=3 * 3600,
                                     printer=out.append), 0)   # =4 h exacto
        st = qs_mod._load_state()
        self.assertEqual(st["requests"], 150)      # cuenta en las 12.000
        self.assertIsNone(st.get("wall_t0"))       # no abre las 40 h
        # tras A6 la preparación queda cerrada
        qs_mod.session_begin("s0")
        self.assertEqual(qs_mod.prep(requests=0, wall_s=0,
                                     printer=out.append), 1)


class TestJEV77Instances(TmpStore):
    """R36 §3: clasificación durable de instancias — transición
    planificada (bloque cerrado → siguiente checkpoint, sin consumir la
    reserva de reinicios), recarga de subsesión (mismo checkpoint) y
    reinicio extraordinario (máx. 4, reserva propia de 288 intentos de
    puertas sobre la total de 612)."""

    def setUp(self):
        super().setUp()
        qs_mod._set_profile("jev77")
        self.addCleanup(qs_mod._set_profile, "jev68")
        qs_mod.prep(requests=0, wall_s=0, printer=lambda *a: None)

    def test_seis_new_session_rechazan_el_quinto(self):
        """Sonda R36: sin trabajo ejecutado seis --new-session seguidos
        son reinicios extraordinarios del mismo checkpoint — el quinto
        supera el máximo presupuestado (4) y se rechaza."""
        st = qs_mod.session_begin("s0")
        self.assertEqual(st["instances"][-1]["reason"], "initial")
        for i in range(1, 5):
            st = qs_mod.session_begin(f"s{i}", new_session=True)
            self.assertEqual(st["instances"][-1]["reason"], "restart")
            self.assertEqual(st["restart_extra"], i)
        with self.assertRaises(SystemExit):
            qs_mod.session_begin("s5", new_session=True)
        # el contador persistido no pasó de 4 (el rechazo no lo muta)
        self.assertEqual(qs_mod._load_state()["restart_extra"], 4)

    def test_restart_no_cambia_checkpoint(self):
        qs_mod.session_begin("s0")
        with self.assertRaises(SystemExit):
            qs_mod.session_begin("s1", new_session=True,
                                 ckpt="gemma3_27b")
        # el bloque activo sigue siendo el inicial: no hubo cambio
        self.assertEqual(qs_mod._load_state()["active_ckpt"],
                         "medgemma27b")

    def test_transition_exige_bloque_cerrado(self):
        """Una transición planificada a gemma3_27b con el bloque de
        medgemma27b aún pendiente se rechaza."""
        qs_mod.session_begin("s0")
        with self.assertRaises(SystemExit):
            qs_mod.session_begin("s1", new_session=True,
                                 reason="transition", ckpt="gemma3_27b")

    def test_subsesion_durable_sin_reset_por_comando(self):
        """La subsesión NO se resetea con gate/run/--resume: sub_t0
        sobrevive a llamadas de la misma sesión (R36 §2); solo lo renueva
        una recarga declarada."""
        st = qs_mod.session_begin("s0")
        sub0 = st["sub_t0"]
        # dos resumes sin recarga: misma subsesión durable
        qs_mod.session_begin("s0")
        st2 = qs_mod.session_begin("s0")
        self.assertEqual(st2["sub_t0"], sub0)
        # una recarga declarada la renueva (reinicio del mismo checkpoint)
        st3 = qs_mod.session_begin("s1", new_session=True)
        self.assertGreater(st3["sub_t0"], sub0)
        self.assertEqual(st3["instances"][-1]["reason"], "restart")

    def test_reason_explicito_subsession(self):
        """La clasificación declarada se honra: recarga de subsesión del
        mismo checkpoint registra 'subsession', no 'restart'."""
        st = qs_mod.session_begin("s0")
        st["sub_t0"] = qs_mod._wall() - 13 * 3600   # subsesión agotada
        qs_mod._save_state(st)
        st2 = qs_mod.session_begin("s1", new_session=True,
                                 reason="subsession")
        self.assertEqual(st2["instances"][-1]["reason"], "subsession")
        self.assertNotIn("restart_extra", st2)

    def test_subsession_anticipada_cuenta_como_restart(self):
        """Sonda R38 §2: `reason='subsession'` con las 12 h sin agotar se
        reclasifica como reinicio extraordinario — consume restart_extra
        y el máximo de 4 igual que un restart (no elude los límites)."""
        qs_mod.session_begin("s0")
        st = qs_mod.session_begin("e1", new_session=True,
                                reason="subsession")
        self.assertEqual(st["instances"][-1]["reason"], "restart")
        self.assertEqual(st["restart_extra"], 1)
        # con el máximo ya gastado, la recarga anticipada se rechaza
        st["restart_extra"] = qs_mod.RESTART_EXTRA_MAX
        qs_mod._save_state(st)
        with self.assertRaises(SystemExit):
            qs_mod.session_begin("e2", new_session=True,
                                 reason="subsession")
        self.assertEqual(qs_mod._load_state()["restart_extra"],
                         qs_mod.RESTART_EXTRA_MAX)
        # seis recargas anticipadas seguidas: ninguna es 'subsession'
        st = qs_mod._load_state()
        st["restart_extra"] = 0
        qs_mod._save_state(st)
        aceptadas = []
        for i in range(6):
            try:
                qs_mod.session_begin(f"early{i}", new_session=True,
                                     reason="subsession")
                aceptadas.append(i)
            except SystemExit:
                break
        st = qs_mod._load_state()
        self.assertEqual(len(aceptadas), qs_mod.RESTART_EXTRA_MAX)
        self.assertEqual(st["restart_extra"], qs_mod.RESTART_EXTRA_MAX)
        self.assertTrue(all(i["reason"] != "subsession"
                            for i in st["instances"] if
                            i["session"].startswith("early")))


class TestJEV77VisibilityR36(TmpStore):
    """R36 §5: control de visibilidad duro — el payload <document> debe
    decodificar EXACTAMENTE al estado del caso y los mensajes efectivos
    deben ser los esperados; en el ciego, ningún mensaje lleva
    instrucciones/criterios/apéndice y la gramática conserva el esquema
    del combo (modo×orden)."""

    def setUp(self):
        super().setUp()
        qs_mod._set_profile("jev77")
        self.addCleanup(qs_mod._set_profile, "jev68")
        self.qs = TRIAGE_QS
        self.combo_g = qs_mod.parse_gate_key(
            "prob_typesafe_off_d0_gemma3_27b")
        self.case = load_phase("triage_es")[1][0]   # T01_ebus_alergia

    def test_estado_sustituido_falla_visible(self):
        """Sonda R36: 'ESTADO SUSTITUIDO' en el payload del usuario es
        violación de visibilidad — no una nota."""
        req = _mk_request(self.qs, thinking=None)
        req["messages"][1]["content"] = "ESTADO SUSTITUIDO"
        rec = _mk_rec(req, usage=300)
        fails = qs_mod._gate_case_fails(
            self.combo_g, "triage_es", self.case.id, rec, self.qs,
            _sha_of(req), {},
            {"triage_es": {self.case.id: 300}}, {}, {})
        self.assertTrue(any("estado" in f for f in fails), fails)

    def test_estado_truncado_falla_visible(self):
        """Estado truncado dentro del <document>: tampoco pasa."""
        req = _mk_request(self.qs, thinking=None,
                          state=self.case.state)
        req["messages"][1]["content"] = (
            "<document>\n"
            + json.dumps(self.case.state[:20], ensure_ascii=False)
            + "\n</document>")
        rec = _mk_rec(req, usage=300)
        fails = qs_mod._case_client_fails(
            self.combo_g, "triage_es/T01", rec, self.qs, _sha_of(req),
            state=self.case.state)
        self.assertTrue(any("estado" in f for f in fails), fails)

    def test_estado_integro_pasa(self):
        """El estado correcto en el payload (como lo serializa el
        adaptador) pasa la vigilancia."""
        req = _mk_request(self.qs, thinking=None, state=self.case.state)
        rec = _mk_rec(req, usage=10)
        self.assertEqual(qs_mod._case_client_fails(
            self.combo_g, "triage_es/T01", rec, self.qs, _sha_of(req),
            state=self.case.state), [])

    def test_ciego_inyeccion_en_user_y_schema_vacio_fallan(self):
        """Sonda R36: instrucciones en el mensaje USER (no solo system)
        y una gramática vacía son fallos del ciego."""
        blind = _mk_request(self.qs, inject=False, thinking=None)
        blind["messages"][1]["content"] = (
            "ESTADO SUSTITUIDO "
            + self.qs["department"]["instructions"])
        blind["response_format"]["json_schema"]["schema"] = {
            "type": "object", "properties": {}}
        brec = _mk_rec(blind, usage=10)
        fails, _ = qs_mod._blind_fails(self.combo_g, "adv1/A01", brec,
                                     self.qs, exp_sha=_sha_of(blind))
        self.assertTrue(any("instrucciones" in f for f in fails), fails)
        self.assertTrue(any("esquema" in f or "schema" in f
                            for f in fails), fails)
        # con la referencia del combo el fallo también se detecta
        vis = _mk_request(self.qs, thinking=None,
                          state=self.case.state)
        schema_v = vis["response_format"]["json_schema"]["schema"]
        fails2, _ = qs_mod._blind_fails(
            self.combo_g, "adv1/A01", brec, self.qs,
            exp_schema=schema_v)
        self.assertTrue(any("schema" in f for f in fails2), fails2)

    def test_ciego_integro_pasa(self):
        """Un ciego legítimo pasa: payload con el estado, sin inyección
        y la gramática íntegra del combo."""
        vis = _mk_request(self.qs, thinking=None, state=self.case.state)
        schema_v = vis["response_format"]["json_schema"]["schema"]
        blind = _mk_request(self.qs, inject=False, thinking=None,
                            state=self.case.state)
        brec = _mk_rec(blind, usage=10)
        fails, _ = qs_mod._blind_fails(
            self.combo_g, "adv1/A01", brec, self.qs,
            exp_sha=_sha_of(blind), state=self.case.state,
            exp_schema=schema_v)
        self.assertEqual(fails, [])

    def test_ciego_schema_conserva_orden_d1(self):
        """La gramática ciega conserva el orden del combo: un schema en
        d0 dentro de un combo d1 se detecta aunque las preguntas estén."""
        combo_d1 = qs_mod.parse_gate_key(
            "prob_typesafe_off_d1_gemma3_27b")
        o1 = {"department": NAMED_ORDERS["department"]["d1"]}
        vis = _mk_request(qs_mod._qs_eff(self.qs, "d1"),
                          thinking=None, state=self.case.state)
        schema_v = vis["response_format"]["json_schema"]["schema"]
        # el ciego con el orden correcto pasa
        blind_ok = _mk_request(qs_mod._qs_eff(self.qs, "d1"),
                               inject=False, thinking=None,
                               state=self.case.state)
        self.assertEqual(qs_mod._blind_fails(
            combo_d1, "adv1/A01", _mk_rec(blind_ok, usage=10),
            qs_mod._qs_eff(self.qs, "d1"), state=self.case.state,
            exp_schema=schema_v)[0], [])
        # y un schema en d0 (mismo contenido, orden distinto) falla
        blind_d0 = _mk_request(self.qs, inject=False, thinking=None,
                               state=self.case.state)
        fails, _ = qs_mod._blind_fails(
            combo_d1, "adv1/A01", _mk_rec(blind_d0, usage=10),
            qs_mod._qs_eff(self.qs, "d1"), state=self.case.state,
            exp_schema=schema_v)
        self.assertTrue(any("schema" in f or "orden" in f
                            for f in fails), fails)


class TestJEV77Blocks(TmpStore):
    """R36 §1/§2: ejecución por bloques con progreso durable — solo el
    checkpoint activo se ejecuta y solo él exige puertas; la transición
    sella el bloque; el deadline del request es el mínimo de los tres
    remanentes (global/celda/subsesión)."""

    def setUp(self):
        super().setUp()
        qs_mod._set_profile("jev77")
        self.addCleanup(qs_mod._set_profile, "jev68")
        self.cells = {n: {**c, "phases": ["triage_es"]}
                      for n, c in qs_mod.CELLS_77.items()}
        self._mp = [mock.patch.object(qs_mod, "CELLS", self.cells),
                    mock.patch.object(qs_mod, "PHASES_ALL",
                                      ["triage_es"]),
                    mock.patch.object(
                        qs_mod, "_verify_manifest",
                        return_value=(None,
                                      {"manifest_sha256": "fake77"}))]
        for p in self._mp:
            p.start()
            self.addCleanup(p.stop)
        qs_mod.prep(requests=0, wall_s=0, printer=lambda *a: None)

    def _factory(self):
        def mk(opts):
            o = json.loads(opts["extra_body"])
            th = ((o.get("chat_template_kwargs") or {})
                  .get("enable_thinking"))
            orders = (resolve_choice_order(opts["choice_order"])
                      if opts.get("choice_order") else None)
            inj = opts["inject_schema_in_prompt"] == "true"
            return _StubModel(usage=640 if inj else 10, inject=inj,
                              thinking=th, mode=opts["mode"],
                              orders=orders)
        return mk

    def _refs(self, key):
        toks = {"triage_es": {c.id: 640
                              for c in load_phase("triage_es")[1]}}
        for ph, c in qs_mod._gate_cases():
            toks.setdefault(ph, {})[c.id] = 640
        qs_mod._refs_path(key).write_text(json.dumps(
            {"meta": {"combo": key}, "tokens": toks}))

    def _gate_block(self, ckpt, session, first=False):
        names = dict(qs_mod.BLOCKS_77)[ckpt]
        for j, n in enumerate(names):
            key = qs_mod.cell_gate_key(self.cells[n])
            self._refs(key)
            ok, det = qs_mod.gate(
                key, session=session,
                new_session=(first and j == 0),
                model_factory=self._factory(),
                printer=lambda *a: None)
            self.assertTrue(ok, det["fails"])

    def test_transition_resume_solo_puertas_del_activo(self):
        """Sonda R36 (transition_resume): con el bloque de medgemma
        cerrado y la transición DECLARADA, la reanudación solo
        comprueba/ejecuta las celdas del checkpoint activo — ninguna
        puerta del checkpoint descargado."""
        for n in dict(qs_mod.BLOCKS_77)["medgemma27b"]:
            _write_run(self.cells[n]["run"], "triage_es", hit=True)
        qs_mod.session_begin("s1")
        # la transición se declara con la nueva instancia (R38 §1) —
        # es la única vía que mueve el checkpoint activo
        qs_mod.session_begin("s2", new_session=True)
        self.assertEqual(qs_mod._load_state()["active_ckpt"],
                         "gemma3_27b")
        checked = []
        orig = qs_mod._cell_gate_ok

        def spy(ctx, cell):
            checked.append(cell.get("ckpt"))
            return orig(ctx, cell)

        with mock.patch.object(qs_mod, "_cell_gate_ok", spy), \
                mock.patch.object(
                    qs_mod.j67, "load_token_ref", _default_hist):
            rc = qs_mod.run(session="s2", resume=True,
                            model_factory=self._factory(),
                            now=mock.Mock(return_value=0.0),
                            sleep=lambda s: None,
                            printer=lambda *a, **k: None)
        self.assertEqual(rc, 2)          # sin puertas del activo
        self.assertEqual(set(checked), {"gemma3_27b"})
        self.assertNotIn("medgemma27b", checked)
        self.assertEqual(qs_mod._load_state()["active_ckpt"],
                         "gemma3_27b")

    def test_slot_completo_no_exige_puerta(self):
        """Slots ya cerrados se saltan ANTES de exigir puerta: en el
        bloque activo, una celda sin pendientes no pide gate."""
        for n in dict(qs_mod.BLOCKS_77)["medgemma27b"][:2]:
            _write_run(self.cells[n]["run"], "triage_es", hit=True)
        for n in dict(qs_mod.BLOCKS_77)["medgemma27b"][2:]:
            key = qs_mod.cell_gate_key(self.cells[n])
            gid = f"{qs_mod._gate_run(key)}@t~u"
            toks = {"triage_es": {c.id: 310 for c in
                                  load_phase("triage_es")[1]}}
            rdoc = {"meta": {"combo": key}, "tokens": toks}
            qs_mod._refs_path(key).write_text(json.dumps(rdoc))
            _write_gate_archive(key, gid, refs_doc=rdoc)
        qs_mod.session_begin("s1")
        checked = []
        orig = qs_mod._cell_gate_ok

        def spy(ctx, cell):
            checked.append(qs_mod.cell_gate_key(cell))
            return orig(ctx, cell)

        out = []
        with mock.patch.object(qs_mod, "_cell_gate_ok", spy), \
                mock.patch.object(qs_mod, "_validate_existing",
                                  lambda *a, **k: None), \
                mock.patch.object(
                    qs_mod.j67, "load_token_ref", _default_hist):
            rc = qs_mod.run(
                session="s1", resume=True,
                model_factory=self._factory(),
                now=mock.Mock(return_value=0.0),
                sleep=lambda s: None,
                printer=lambda *a, **k: out.append(
                    " ".join(map(str, a))))
        self.assertEqual(rc, 2)
        # las celdas con slots completos (MD0, MP0) nunca piden puerta
        self.assertEqual(
            sorted(checked),
            sorted(qs_mod.cell_gate_key(self.cells[n])
                   for n in ("MD1", "MP1")))
        st = qs_mod._load_state()
        self.assertEqual(st["blocks_done"], ["medgemma27b"])
        self.assertTrue(any("TRANSICIÓN" in linea
                            and "gemma3_27b" in linea for linea in out))

    def test_retry_errors_permanece_en_el_bloque(self):
        """Sonda R38 (block_probe): con el bloque medgemma cerrado salvo
        un error de transporte, --retry-errors reintenta DENTRO del
        bloque — nunca pide puertas del siguiente checkpoint ni sella
        ni mueve el activo."""
        for n in dict(qs_mod.BLOCKS_77)["medgemma27b"]:
            _write_run(self.cells[n]["run"], "triage_es", hit=True)
        d = store.load(self.cells["MD0"]["run"], "triage_es")
        cid = next(iter(d["cases"]))
        d["cases"][cid] = {"error": "transport failure"}
        store.save(self.cells["MD0"]["run"], "triage_es", d)
        qs_mod.session_begin("s0")
        checked = []
        with mock.patch.object(
                qs_mod, "_cell_gate_ok",
                side_effect=lambda ctx, cell: (
                    checked.append(cell["ckpt"]), False)[1]), \
                mock.patch.object(qs_mod, "_validate_existing",
                                  lambda *a, **k: None):
            rc = qs_mod.run(session="s0", resume=True,
                            retry_errors=True,
                            model_factory=self._factory(),
                            now=mock.Mock(return_value=0.0),
                            sleep=lambda s: None,
                            printer=lambda *a, **k: None)
        self.assertEqual(rc, 2)
        self.assertEqual(checked, ["medgemma27b"])   # solo el activo
        st = qs_mod._load_state()
        self.assertEqual(st["active_ckpt"], "medgemma27b")
        self.assertNotIn("medgemma27b", st.get("blocks_done") or [])
        self.assertEqual(len(st["instances"]), 1)
        # el error sigue presente: ni se reintentó fuera de bloque ni
        # el bloque quedó sellado
        self.assertIn("error", store.load(self.cells["MD0"]["run"],
                                          "triage_es")["cases"][cid])

    def test_bloque_cerrado_exige_transicion_declarada(self):
        """R38 §1: un run con el bloque activo cerrado NO avanza el
        checkpoint servido — anuncia TRANSICIÓN PENDIENTE y espera la
        instancia declarada (--new-session/begin), que es la única vía
        que mueve active_ckpt con registro durable."""
        for n in dict(qs_mod.BLOCKS_77)["medgemma27b"]:
            _write_run(self.cells[n]["run"], "triage_es", hit=True)
        qs_mod.session_begin("s0")
        out = []
        with mock.patch.object(qs_mod, "_validate_existing",
                               lambda *a, **k: None):
            rc = qs_mod.run(
                session="s0", resume=True,
                model_factory=self._factory(),
                now=mock.Mock(return_value=0.0), sleep=lambda s: None,
                printer=lambda *a, **k: out.append(
                    " ".join(map(str, a))))
        self.assertEqual(rc, 2)
        self.assertTrue(any("TRANSICIÓN PENDIENTE" in linea
                            for linea in out))
        st = qs_mod._load_state()
        self.assertEqual(st["active_ckpt"], "medgemma27b")
        self.assertEqual(st["blocks_done"], ["medgemma27b"])
        self.assertEqual(len(st["instances"]), 1)     # sin transición
        # solo tras declarar la instancia nueva el checkpoint avanza
        st = qs_mod.session_begin("s1", new_session=True)
        self.assertEqual(st["active_ckpt"], "gemma3_27b")
        self.assertEqual(st["instances"][-1]["reason"], "transition")

    def test_deadline_es_minimo_de_los_tres_remanentes(self):
        """Sonda R36: con 1 s de subsesión el deadline armado es ~1 s,
        no el presupuesto de celda ni el de sesión."""
        st = {"session": "s1", "started": "x", "elapsed_s": 0.0,
              "requests": 0, "cell_s": {}, "retried": {},
              "sessions": ["s1"], "wall_t0": qs_mod._wall() - 100,
              "sub_t0": qs_mod._wall()
              - (qs_mod.PROFILES["jev77"]["subsession_cap_s"] - 1)}
        cell = {**self.cells["MD0"], "budget_s": 10 * 3600}
        key = qs_mod.cell_gate_key(cell)
        ctx = _ctx({"MD0": cell}, st=st,
                   hist={c.id: 310 for c in load_phase("triage_es")[1]})
        ctx["refs_on"][key] = {
            "triage_es": {c.id: 310
                          for c in load_phase("triage_es")[1]}}
        armed = []

        class Armed:
            def __init__(self, inner):
                self.target = self
                self.inner = inner
                self.calls = 0
            def meta(self):
                return self.inner.meta()
            def expected_system_prompt_sha256(self, q):
                return self.inner.expected_system_prompt_sha256(q)
            def arm_external_deadline(self, s):
                self.armed = armed
                armed.append(s)
            def decide(self, *a, **k):
                return self.inner.decide(*a, **k)

        ctx["models"]["MD0"] = Armed(
            _StubModel(usage=310, inject=True, thinking=None))
        qs_mod._exec_slot(ctx, "MD0", "triage_es", False,
                          mock.Mock(return_value=0.0), lambda s: None,
                          lambda *a, **k: None)
        self.assertTrue(armed)
        self.assertAlmostEqual(armed[0], 1.0, places=1)

    def test_integrado_cinco_bloques_cuatro_transiciones(self):
        """Prueba integrada R36: 5 bloques, 4 transiciones planificadas,
        un reinicio extraordinario dentro de un bloque y reanudación —
        progreso durable, puertas solo del checkpoint activo y
        procedencia correcta por caso."""
        blocks = list(qs_mod.BLOCKS_77)
        checked = []
        orig_gate_ok = qs_mod._cell_gate_ok

        def spy(ctx, cell):
            checked.append(qs_mod.cell_gate_key(cell))
            return orig_gate_ok(ctx, cell)

        out = []
        printer = lambda *a, **k: out.append(" ".join(map(str, a)))
        factory = self._factory()
        pause_calls = [0]

        def pause_flip():
            pause_calls[0] += 1
            return pause_calls[0] > 3   # para el bloque 1 a mitad

        st0 = qs_mod.session_begin("s0")   # A6 tras A3
        self.assertEqual(st0["active_ckpt"], "medgemma27b")
        self._gate_block("medgemma27b", "s0")
        # bloque 1 completo → transición sellada
        with mock.patch.object(qs_mod, "_cell_gate_ok", spy), \
                mock.patch.object(qs_mod.j67, "load_token_ref",
                                  _default_hist):
            rc = qs_mod.run(session="s0", model_factory=factory,
                            now=mock.Mock(return_value=0.0),
                            sleep=lambda s: None, printer=printer)
        self.assertEqual(rc, 2)
        self.assertEqual(qs_mod._load_state()["blocks_done"],
                         ["medgemma27b"])
        # bloque 2 (gemma3_27b): puertas bajo nueva instancia; un
        # reinicio extraordinario a mitad conserva el progreso y la
        # reanudación termina el bloque
        self._gate_block("gemma3_27b", "s1", first=True)
        st = qs_mod._load_state()
        self.assertEqual(st["active_ckpt"], "gemma3_27b")
        self.assertEqual(st["instances"][-1]["reason"], "transition")
        with mock.patch.object(qs_mod, "_cell_gate_ok", spy), \
                mock.patch.object(qs_mod.j67, "load_token_ref",
                                  _default_hist), \
                mock.patch.object(qs_mod, "_pause_requested",
                                  side_effect=pause_flip):
            rc = qs_mod.run(session="s1", resume=True,
                            model_factory=factory,
                            now=mock.Mock(return_value=0.0),
                            sleep=lambda s: None, printer=printer)
        self.assertEqual(rc, 2)          # pausa: bloque aún pendiente
        st = qs_mod._load_state()
        self.assertEqual(st["active_ckpt"], "gemma3_27b")
        self.assertNotIn("gemma3_27b", st.get("blocks_done", []))
        # reinicio extraordinario del MISMO checkpoint + nuevas puertas
        self._gate_block("gemma3_27b", "s1b", first=True)
        st = qs_mod._load_state()
        self.assertEqual(st["instances"][-1]["reason"], "restart")
        self.assertEqual(st["restart_extra"], 1)
        self.assertEqual(st["gate_spend"]["restart"], 24)
        with mock.patch.object(qs_mod, "_cell_gate_ok", spy), \
                mock.patch.object(qs_mod.j67, "load_token_ref",
                                  _default_hist):
            rc = qs_mod.run(session="s1b", resume=True,
                            model_factory=factory,
                            now=mock.Mock(return_value=0.0),
                            sleep=lambda s: None, printer=printer)
        self.assertEqual(rc, 2)          # transición a qwen38fp8
        self.assertEqual(qs_mod._load_state()["blocks_done"],
                         ["medgemma27b", "gemma3_27b"])
        # bloques 3-5 en serie, cada uno con su instancia y sus puertas
        sess = {3: "s2", 4: "s3", 5: "s4"}
        for i, (ck, _) in enumerate(blocks[2:], start=3):
            self._gate_block(ck, sess[i], first=True)
            st = qs_mod._load_state()
            self.assertEqual(st["active_ckpt"], ck)
            self.assertEqual(st["instances"][-1]["reason"], "transition")
            with mock.patch.object(qs_mod, "_cell_gate_ok", spy), \
                    mock.patch.object(qs_mod.j67, "load_token_ref",
                                      _default_hist):
                rc = qs_mod.run(session=sess[i], resume=True,
                                model_factory=factory,
                                now=mock.Mock(return_value=0.0),
                                sleep=lambda s: None,
                                printer=printer)
        self.assertEqual(rc, 0)          # encargo completo
        st = qs_mod._load_state()
        self.assertEqual(st["blocks_done"], [ck for ck, _ in blocks])
        self.assertEqual(st["restart_extra"], 1)
        # procedencia: cada caso lleva sesión, checkpoint y gate_id
        for n, c in self.cells.items():
            doc = store.load(c["run"], "triage_es")
            self.assertTrue(doc["cases"], c["run"])
            for rec in doc["cases"].values():
                self.assertEqual(rec.get("ckpt"), c["ckpt"], c["run"])
                self.assertTrue(rec.get("gate_id"), c["run"])
        # ninguna puerta consultada fuera del bloque activo en su pasada
        for k in checked:
            self.assertTrue(k.endswith(
                tuple("_" + ck for ck, _ in blocks)), k)


class TestJEV77CascadeAudit(TmpStore):
    """R36 §7: cascada parcial → NO EVALUABLE con su nota, y la
    auditoría exige procedencia congelada (d1, revisor/versión, host,
    manifiesto)."""

    def setUp(self):
        super().setUp()
        qs_mod._set_profile("jev77")
        self.addCleanup(qs_mod._set_profile, "jev68")
        self._man_sha = "m77"      # `_write_manifest` lo sustituye

    def _write_manifest(self):
        """Manifiesto congelado mínimo y COHERENTE con las políticas
        efectivas de cascada — sha declarado recalculado del contenido
        (el auditor lo verifica, R39 §3)."""
        man = {"policies": {"cascade": {
                   "requests": qs_mod.JEV77_CASCADE_REQUESTS,
                   "wall_s": qs_mod.JEV77_CASCADE_WALL_S,
                   "raw": qs_mod.JEV77_CASCADE_RAW,
                   "audit": qs_mod.JEV77_CASCADE_AUDIT,
                   "reviewer": dict(qs_mod.JEV77_CASCADE_REVIEWER)}},
               "cells": {"MD0": {"run": qs_mod.CELLS_77["MD0"]["run"]}}}
        man["manifest_sha256"] = qs_mod._manifest_content_sha(man)
        self._man_sha = man["manifest_sha256"]
        (self.tmp / "logs" / "qwen_manifest_jev77.json").write_text(
            json.dumps(man))

    def _write_budget(self, **over):
        """Registro durable de la cascada completo y acreditado."""
        b = {"requests": 700, "started_wall": 0.0,
             "session": "s0",
             "reviewer": {"provider": "openrouter",
                          "model": "~typesafe/jev-latest",
                          "adapter": "jev",
                          "resolved": "jev-1.14-20261101"}}
        b.update(over)
        (self.tmp / "logs" / "jev77_cascade.json").write_text(
            json.dumps(b))

    def _write_cascade_phase(self, ph, version="jev-1.14-20261101"):
        from jevbench import cascade as _casc
        qs, cases = load_phase(ph)
        rqs = _casc.review_questions(qs, ph)
        raw = {"meta": {"d1": qs_mod.CELLS_77["MD0"]["run"],
                        "reviewer": "jev", "host": "h",
                        "provider": "openrouter",
                        "model": "~typesafe/jev-latest",
                        "session": "s0",
                        "manifest_sha256": self._man_sha,
                        "questions_hash": questions_hash(rqs),
                        "reviewer_resolved": version},
               "cases": {}}
        aud = {"meta": {"d1": qs_mod.CELLS_77["MD0"]["run"],
                        "raw": qs_mod.JEV77_CASCADE_RAW, "host": "h",
                        "session": "s0",
                        "manifest_sha256": self._man_sha},
               "cases": {}}
        for c in cases:
            a = _answers_hit(qs, c.gt)
            raw["cases"][c.id] = {"answers": a,
                                  "reviewer_version": version}
            aud["cases"][c.id] = {"answers": a}
        store.save(qs_mod.JEV77_CASCADE_RAW, ph, raw)
        store.save(qs_mod.JEV77_CASCADE_AUDIT, ph, aud)

    def test_cascada_parcial_no_evaluable(self):
        """Sonda R36: una sola fase auditada de 11 no produce delta
        pareado válido — se publica como parcialidad NO EVALUABLE."""
        (self.tmp / "logs" / "jev77_cascade.json").write_text(
            json.dumps({"requests": 10, "started_wall": 0.0}))
        self._write_cascade_phase("triage_es")
        rep = qs_mod._audit_cascade77()
        self.assertFalse(rep["evaluable"])
        self.assertEqual(rep["missing"], [ph for ph in qs_mod.PHASES_ALL
                                        if ph != "triage_es"])
        self.assertIn("cobertura parcial", rep["note"])

    def test_cascada_completa_evaluable(self):
        self._write_budget()
        self._write_manifest()
        for ph in qs_mod.PHASES_ALL:
            self._write_cascade_phase(ph)
        rep = qs_mod._audit_cascade77()
        self.assertTrue(rep["evaluable"], rep)
        self.assertEqual(rep["versions"], ["jev-1.14-20261101"])

    def test_parada_persistida_no_evaluable(self):
        """Un 'stopped' durable en el registro del cupo invalida el
        contraste aunque la cobertura estuviera completa."""
        (self.tmp / "logs" / "jev77_cascade.json").write_text(
            json.dumps({"requests": 10, "started_wall": 0.0,
                        "stopped": {"reason": "DeadlineExceeded"}}))
        for ph in qs_mod.PHASES_ALL:
            self._write_cascade_phase(ph)
        rep = qs_mod._audit_cascade77()
        self.assertFalse(rep["evaluable"])
        self.assertIn("parada", rep["note"])

    def test_versiones_mezcladas_no_evaluable(self):
        (self.tmp / "logs" / "jev77_cascade.json").write_text(
            json.dumps({"requests": 10, "started_wall": 0.0}))
        self._write_cascade_phase("triage_es", version="jev-a")
        self._write_cascade_phase("adv1", version="jev-b")
        rep = qs_mod._audit_cascade77()
        self.assertFalse(rep["evaluable"])
        self.assertTrue(any("mezcladas" in b for b in rep["bad_meta"]))

    def test_cupo_excedido_y_version_ausente_no_evaluable(self):
        """Sonda R38 §7: el registro con más intentos que el cupo
        congelado, o casos raw sin reviewer_version, invalidan aunque
        la cobertura de las 11 fases esté completa."""
        (self.tmp / "logs" / "jev77_cascade.json").write_text(
            json.dumps({"requests": 801, "started_wall": 0.0}))
        self._write_manifest()
        for ph in qs_mod.PHASES_ALL:
            self._write_cascade_phase(ph)
        rep = qs_mod._audit_cascade77()
        self.assertFalse(rep["evaluable"], rep)
        self.assertTrue(any("cupo" in b for b in rep["bad_meta"]),
                        rep["bad_meta"])
        # y sin versión por caso — ausente en TODOS — igual de inválido
        (self.tmp / "logs" / "jev77_cascade.json").write_text(
            json.dumps({"requests": 700, "started_wall": 0.0}))
        for ph in qs_mod.PHASES_ALL:
            d = store.load(qs_mod.JEV77_CASCADE_RAW, ph)
            for rec in d["cases"].values():
                rec.pop("reviewer_version", None)
            store.save(qs_mod.JEV77_CASCADE_RAW, ph, d)
        rep2 = qs_mod._audit_cascade77()
        self.assertFalse(rep2["evaluable"], rep2)
        self.assertTrue(any("reviewer_version" in b
                            for b in rep2["bad_meta"]),
                        rep2["bad_meta"])

    def test_fusion_sin_procedencia_no_evaluable(self):
        """La fusión debe conservar la procedencia del encargo
        (host + manifest_sha256) — ausente invalida."""
        (self.tmp / "logs" / "jev77_cascade.json").write_text(
            json.dumps({"requests": 10, "started_wall": 0.0}))
        self._write_manifest()
        for ph in qs_mod.PHASES_ALL:
            self._write_cascade_phase(ph)
        d = store.load(qs_mod.JEV77_CASCADE_AUDIT, "triage_es")
        d["meta"].pop("manifest_sha256", None)
        store.save(qs_mod.JEV77_CASCADE_AUDIT, "triage_es", d)
        rep = qs_mod._audit_cascade77()
        self.assertFalse(rep["evaluable"], rep)
        self.assertTrue(any("fusión" in b for b in rep["bad_meta"]),
                        rep["bad_meta"])

    def _baseline_evaluable(self):
        """Fixture completo y acreditado de las 11 fases."""
        self._write_budget()
        self._write_manifest()
        for ph in qs_mod.PHASES_ALL:
            self._write_cascade_phase(ph)
        rep = qs_mod._audit_cascade77()
        self.assertTrue(rep["evaluable"], rep)

    def test_metadatos_incompatibles_no_evaluable(self):
        """Sonda R39 §3: procedencia PRESENTE pero incompatible en raw
        o fusión invalida igual que la ausente — hash, preguntas,
        proveedor/modelo y sesión se cotejan contra el encargo."""
        mutaciones = [
            ("fusion_sha", qs_mod.JEV77_CASCADE_AUDIT,
             lambda m: m.update(manifest_sha256="another_encargo")),
            ("raw_qhash", qs_mod.JEV77_CASCADE_RAW,
             lambda m: m.update(questions_hash="foreign_questions")),
            ("raw_provider", qs_mod.JEV77_CASCADE_RAW,
             lambda m: m.update(provider="typesafe",
                                model="foreign_model")),
            ("raw_session", qs_mod.JEV77_CASCADE_RAW,
             lambda m: m.update(session="foreign_session")),
        ]
        for nombre, run, mut in mutaciones:
            with self.subTest(nombre):
                self._baseline_evaluable()
                doc = store.load(run, "triage_es")
                old = copy.deepcopy(doc)
                mut(doc["meta"])
                store.save(run, "triage_es", doc)
                rep = qs_mod._audit_cascade77()
                self.assertFalse(rep["evaluable"], rep)
                self.assertTrue(rep["bad_meta"], rep)
                store.save(run, "triage_es", old)

    def test_manifiesto_sin_sha_valido_no_evaluable(self):
        """El manifiesto auditado exige sha declarado Y coherente con
        el contenido — ausente o incoherente invalida."""
        self._baseline_evaluable()
        mp = self.tmp / "logs" / "qwen_manifest_jev77.json"
        man = json.loads(mp.read_text())
        man.pop("manifest_sha256")
        mp.write_text(json.dumps(man))
        rep = qs_mod._audit_cascade77()
        self.assertFalse(rep["evaluable"], rep)
        self.assertTrue(any("sha" in b for b in rep["bad_meta"]),
                        rep["bad_meta"])
        # y un sha declarado que no cuadra con el contenido
        man["manifest_sha256"] = "0" * 16
        mp.write_text(json.dumps(man))
        rep = qs_mod._audit_cascade77()
        self.assertFalse(rep["evaluable"], rep)

    def test_contador_negativo_no_evaluable(self):
        """Un contador de red negativo (o no entero) no es un gasto
        válido — la auditoría lo marca."""
        self._baseline_evaluable()
        self._write_budget(requests=-1)
        rep = qs_mod._audit_cascade77()
        self.assertFalse(rep["evaluable"], rep)
        self.assertTrue(any("cupo" in b for b in rep["bad_meta"]),
                        rep["bad_meta"])

    def test_presupuesto_sin_identidad_a4_no_evaluable(self):
        """Sonda R40 §2: la identidad A4 congelada del revisor es
        obligatoria en el presupuesto — ausente o incompleta invalida
        aunque raw/fusión estén completos."""
        # sin revisor en absoluto
        self._baseline_evaluable()
        (self.tmp / "logs" / "jev77_cascade.json").write_text(json.dumps(
            {"requests": 700, "started_wall": 0.0, "session": "s0"}))
        rep = qs_mod._audit_cascade77()
        self.assertFalse(rep["evaluable"], rep)
        self.assertTrue(any("revisor" in b for b in rep["bad_meta"]),
                        rep["bad_meta"])
        # y falta de cada campo de la identidad
        for campo in ("adapter", "provider", "model", "resolved"):
            with self.subTest(campo):
                self._baseline_evaluable()
                self._write_budget()
                bp = self.tmp / "logs" / "jev77_cascade.json"
                b = json.loads(bp.read_text())
                b["reviewer"].pop(campo)
                bp.write_text(json.dumps(b))
                rep = qs_mod._audit_cascade77()
                self.assertFalse(rep["evaluable"], rep)
                self.assertTrue(
                    any(f"revisor.{campo}" in x for x in rep["bad_meta"]),
                    rep["bad_meta"])

    def test_presupuesto_y_raw_ajenos_al_contrato_no_evaluable(self):
        """Sonda R40 §2: presupuesto y raw coherentes ENTRE SÍ pero
        ajenos al contrato congelado del manifiesto → NO EVALUABLE."""
        self._baseline_evaluable()
        self._write_budget(reviewer={"provider": "typesafe",
                                     "model": "jev-latest",
                                     "adapter": "jev",
                                     "resolved": "jev-1.14-20261101"})
        for ph in qs_mod.PHASES_ALL:
            d = store.load(qs_mod.JEV77_CASCADE_RAW, ph)
            d["meta"].update(provider="typesafe", model="jev-latest")
            store.save(qs_mod.JEV77_CASCADE_RAW, ph, d)
        rep = qs_mod._audit_cascade77()
        self.assertFalse(rep["evaluable"], rep)
        self.assertTrue(any("contrato" in b for b in rep["bad_meta"]),
                        rep["bad_meta"])

    def test_raw_con_adaptador_ajeno_no_evaluable(self):
        """raw.meta.reviewer debe ser el adaptador congelado en el
        presupuesto — otro adaptador invalida."""
        self._baseline_evaluable()
        d = store.load(qs_mod.JEV77_CASCADE_RAW, "triage_es")
        d["meta"]["reviewer"] = "llm"
        store.save(qs_mod.JEV77_CASCADE_RAW, "triage_es", d)
        rep = qs_mod._audit_cascade77()
        self.assertFalse(rep["evaluable"], rep)
        self.assertTrue(any("adaptador" in b for b in rep["bad_meta"]),
                        rep["bad_meta"])


class TestJEV77ManifestPolicies(TmpStore):
    """R36 §6: las políticas del encargo (reloj, subsesión, A3,
    instancias, reservas, cascada) quedan congeladas en el manifiesto
    jev77 — cambiarlas cambia el sha; jev68/jev76 no llevan 'policies'."""

    def setUp(self):
        super().setUp()
        qs_mod._set_profile("jev77")
        self.addCleanup(qs_mod._set_profile, "jev68")

    def test_politicas_cambian_el_sha(self):
        """Sonda R36: clock/subsession_cap_s y las reservas nuevas están
        en el manifiesto — la misma fuente con otra política da otro sha."""
        sha1 = qs_mod._plan_manifest()["manifest_sha256"]
        for attr, val in (("clock", "monotonic"),
                          ("subsession_cap_s", 6 * 3600)):
            with mock.patch.dict(qs_mod.PROFILES["jev77"],
                                 {attr: val}):
                self.assertNotEqual(
                    qs_mod._plan_manifest()["manifest_sha256"], sha1,
                    attr)
        for const in ("RESTART_EXTRA_MAX", "RESTART_GATE_RESERVE",
                      "GATE_RESERVE_TOTAL", "PREP_MAX_REQUESTS",
                      "JEV77_CASCADE_WALL_S"):
            with mock.patch.object(qs_mod, const, 999):
                self.assertNotEqual(
                    qs_mod._plan_manifest()["manifest_sha256"], sha1,
                    const)

    def test_sin_policies_en_perfiles_historicos(self):
        for prof in ("jev68", "jev76"):
            qs_mod._set_profile(prof)
            man = qs_mod._plan_manifest()
            self.assertNotIn("policies", man)
        qs_mod._set_profile("jev77")
