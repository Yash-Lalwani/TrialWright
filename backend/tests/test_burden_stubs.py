from preflight import burden
from preflight.burden._graph_compat import ProtocolGraph
from preflight.burden.models import BurdenReport, PeerSet, PrecedentTable

try:
    G = ProtocolGraph(protocol_id="prt_t", meta={"title": "t"})
except Exception:  # A's real graph needs more fields; stubs ignore the graph anyway
    G = None


def test_stub_shapes_validate():
    peers = burden.find_peers(G)
    assert isinstance(peers, PeerSet) and peers.n == 143
    assert isinstance(burden.compute_burden(G, peers), BurdenReport)
    assert isinstance(burden.precedent(G, peers), PrecedentTable)
    assert burden.burden_score(burden.compute_burden(G, peers)) == 58.0


def test_hotspot_issues_match_peer_ids_and_category():
    peers = burden.find_peers(G)
    issues = burden.hotspots(G, peers)
    assert [i.id for i in issues] == peers.hotspot_issue_ids
    assert {i.category for i in issues} == {"amendment_risk"}
    assert all(i.why.amendment_category == "eligibility" for i in issues)
