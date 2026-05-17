from shared.researchnet_common import h_index, i10_index, impact_factor, indexing_rate_per_hour, ndcg_at_k, precision_at_k


def test_precision_and_ndcg() -> None:
    ranked = ["a", "b", "c", "d"]
    relevant = ["a", "c"]
    assert precision_at_k(ranked, relevant, k=2) == 0.5
    assert ndcg_at_k(ranked, relevant, k=4) > 0



def test_h_index_and_i10() -> None:
    citations = [22, 14, 12, 9, 6, 3]
    assert h_index(citations) == 5
    assert i10_index(citations) == 3



def test_impact_factor_and_rate() -> None:
    assert impact_factor(84, 21) == 4.0
    assert indexing_rate_per_hour(1000, 60) == 1000
