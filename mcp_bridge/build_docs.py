"""Regenerate schema reference and self-contained, locally hosted HTML guides."""
import html
import json
import re
import shutil
import markdown
from .catalog import TOOLS
from .server import ROOT, RESOURCES

def build():
    lines=['# MCP tool reference','',f'{len(TOOLS)} tools. Schemas are generated from `mcp_bridge/catalog.py`. Required fields are explicit; omitted optional values use upstream defaults. IDs and coordinates in examples are placeholders. See [the full capability guide](mcp.md) before making changes.','']
    for name,s in TOOLS.items():
        lines.extend(['## '+name,'',s['description'],'',f"Access: {'read-only' if s['read'] else 'mutation'}. Route: `{('/api/command/'+s['action']) if s['action'] else (s['path'] or 'adapter operation')}`.",'','Input schema:','','```json',json.dumps(s['schema'],indent=2),'```',''])
        if s['example']:lines.extend(['Example arguments (resolve IDs/points first):','','```json',json.dumps(s['example'],indent=2),'```',''])
    # Exact authored preset definitions are simple JS object literals; copy their
    # source verbatim rather than maintain a second set of camera coordinates.
    source=(ROOT/'static/sensor-view.js').read_text()
    presets=re.search(r'export const cabinPresets=(\{.*?\n\});',source,re.S).group(1)
    lines.extend(['## Cabin preset objects','','The WebUI draft definitions below use JavaScript object notation. Convert to JSON, preserving mount and attributes, and include them in the complete `sensors` list. `coverage` adds all three with unique names.','','```javascript',presets,'```',''])
    (ROOT/'docs/mcp-tools.md').write_text('\n'.join(lines))
    for stem in ('mcp','mcp-tools'):
        source=(ROOT/f'docs/{stem}.md').read_text()
        source=source.replace('(mcp-tools.md)','(/mcp-tools.html)').replace('(mcp.md)','(/mcp.html)')
        md=markdown.Markdown(extensions=['fenced_code','tables','toc']);body=md.convert(source)
        page='''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>CARLA MCP documentation</title><style>
:root{color-scheme:light dark;--bg:#f5f7fa;--fg:#182a3c;--panel:#fff;--line:#d8e1ea;--accent:#285fc3}*{box-sizing:border-box}body{overflow-wrap:anywhere;margin:0;background:var(--bg);color:var(--fg);font:16px/1.65 system-ui,sans-serif}header{padding:18px 28px;background:var(--panel);border-bottom:1px solid var(--line);display:flex;gap:24px;flex-wrap:wrap}a{color:var(--accent)}.layout{display:grid;grid-template-columns:260px minmax(0,1080px);max-width:1450px;margin:auto;gap:30px;padding:28px}nav{min-width:0;position:sticky;top:18px;align-self:start;max-height:92vh;overflow:auto;font-size:13px}nav ul{list-style:none;padding-left:12px}nav li{margin:5px 0}main{min-width:0;background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:36px}h1,h2,h3{overflow-wrap:anywhere}h1{font-size:32px;line-height:1.2}h2{margin-top:42px;border-bottom:1px solid var(--line);padding-bottom:8px}h3{margin-top:30px}pre{white-space:pre-wrap;overflow-wrap:anywhere;padding:18px;background:var(--bg);border:1px solid var(--line);border-radius:8px;overflow:auto;font-size:13px}code{font-size:.9em;overflow-wrap:anywhere}table{width:100%;border-collapse:collapse;font-size:14px;display:block;overflow:auto}td,th{padding:12px;text-align:left;vertical-align:top;border:1px solid var(--line)}th{background:var(--bg)}@media(prefers-color-scheme:dark){:root{--bg:#101923;--fg:#d9e6f1;--panel:#172433;--line:#354354;--accent:#87b8ff}}@media(max-width:800px){.layout{display:block;padding:12px}nav{position:static;max-height:240px;margin-bottom:18px}main{padding:18px}h1{font-size:26px}}@media print{nav,header{display:none}.layout{display:block}main{border:0}pre{white-space:pre-wrap}}
</style></head><body><header><strong>CARLA · MCP</strong><a href="/">Simulation workspace</a><a href="/parking-review.html">Parking survey</a><a href="/mcp.html">Capability guide</a><a href="/mcp-tools.html">49 tool schemas</a><a href="/mcp-guide.md" download>Download guide</a><a href="/mcp-tools.md" download>Download schemas</a></header><div class="layout"><nav aria-label="Contents">'''+md.toc+'</nav><main>'+body+'</main></div></body></html>'
        (ROOT/f'static/{stem}.html').write_text(page)
    shutil.copyfile(ROOT/'docs/mcp.md',ROOT/'static/mcp-guide.md')
    shutil.copyfile(ROOT/'docs/mcp-tools.md',ROOT/'static/mcp-tools.md')
    (ROOT/'static/mcp-capabilities.json').write_text(json.dumps({'tools':TOOLS,'resources':list(RESOURCES)},indent=2))

if __name__=='__main__':build()
