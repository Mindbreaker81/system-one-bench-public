// JEV-94/R103: smoke DOM de la ficha servida. Ejecuta los scripts de la página
// generada (inline + src resueltos en disco) sobre un DOM mínimo y vuelca JSON:
// options del selector, configuración elegida, ids creados y texto por sección.
// Uso: node tests/profile_dom.js <pagina.html> [hash]
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const page = process.argv[2];
const hash = process.argv[3] || "";
const dir = path.dirname(page);
const html = fs.readFileSync(page, "utf8");

const byId = {};
const staticIds = new Set();

class Node {}
class TextNode extends Node {
  constructor(t) { super(); this._t = String(t); }
  get innerText() { return this._t; }
}
class El extends Node {
  constructor(tag) { super(); this.tagName = tag.toUpperCase(); this.children = []; this.attrs = {}; this._t = ""; }
  setAttribute(k, v) { this.attrs[k] = String(v); if (k === "id") byId[String(v)] = this; }
  getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; }
  append(...kids) { for (const k of kids) this.children.push(k instanceof Node ? k : new TextNode(k)); }
  appendChild(k) { this.children.push(k); return k; }
  // Como el DOM real: un null/undefined pasa a ser el nodo de texto "null"/"undefined".
  replaceChildren(...kids) { this.children = kids.map(k => k instanceof Node ? k : new TextNode(k)); }
  addEventListener() {}
  get innerText() { return this._t + this.children.map(c => c.innerText).join(""); }
  get textContent() { return this.innerText; }
  set textContent(v) { this.children = []; this._t = String(v); }
  get value() { return this._v !== undefined ? this._v : (this.children[0] ? this.children[0].getAttribute("value") : undefined); }
  set value(v) { this._v = v; }
}

for (const [id, tag] of [["cfg", "select"], ["ident", "div"], ["adj", "div"],
                         ["sets", "div"], ["cal", "div"], ["cost", "div"], ["casc", "div"]]) {
  const e = new El(tag);
  e.setAttribute("id", id);
  staticIds.add(id);
}

const document = {
  createElement: t => new El(t),
  createElementNS: (ns, t) => new El(t),
  createTextNode: t => new TextNode(t),
  querySelector: s => (s[0] === "#" ? (byId[s.slice(1)] || null) : null),
  querySelectorAll: () => [],
  body: new El("body"),
  documentElement: new El("html"),
  title: "",
};

const ctx = vm.createContext({
  document, Node, console,
  location: { hash, pathname: "/" + path.basename(page) },
  history: { replaceState() {} },
  addEventListener() {},
});

const re = /<script(?:\s+src="([^"]+)")?\s*>([\s\S]*?)<\/script>/g;
let m, order = 0;
const missing = [];
while ((m = re.exec(html))) {
  order++;
  let code;
  if (m[1]) {
    const f = path.join(dir, m[1]);
    try { code = fs.readFileSync(f, "utf8"); }
    catch { missing.push(m[1]); continue; }
  } else code = m[2];
  vm.runInContext(code, ctx, { filename: m[1] || `inline#${order}` });
}

const firstH2 = byId.ident.children.find(c => c.tagName === "H2") || null;
console.log(JSON.stringify({
  missing_scripts: missing,
  title: document.title,
  cfg: byId.cfg.value,
  options: byId.cfg.children.map(o => o.getAttribute("value")),
  h_ident: firstH2 ? firstH2.getAttribute("id") : null,
  created_ids: Object.keys(byId).filter(k => !staticIds.has(k)),
  text: Object.fromEntries(["ident", "adj", "sets", "cal", "cost", "casc"]
    .map(id => [id, byId[id].innerText])),
}));
