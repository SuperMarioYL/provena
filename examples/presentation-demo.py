import json,tempfile
from pathlib import Path
from provena.core.graph import ClaimDependencyGraph
from provena.core.provenance import record_claim
from provena.core.source import FileSpan
from provena.core.cascade import CascadeEngine
with tempfile.TemporaryDirectory() as tmp:
 path=Path(tmp)/'source.txt';path.write_text('limit=10\n')
 graph=ClaimDependencyGraph();source=FileSpan.from_file(path,1,1)
 first=record_claim(graph,'The limit is ten.',[source],claim_id='limit')
 record_claim(graph,'A request of eleven exceeds the limit.',[],[first.id],claim_id='request')
 engine=CascadeEngine(graph)
 print('before:',json.dumps({c.id:c.status.value for c in graph.claims()}))
 path.write_text('limit=20\n');print('flagged:',engine.check_all())
 print('after:',json.dumps({c.id:c.status.value for c in graph.claims()}))
