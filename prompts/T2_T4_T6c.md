Your objective is to propose a simple implementation of hypergraph-aware constrained hierarchical agglomeration with semantic similarity in notes/hypergraph_clustering_review_perplexity.md report documenting all design decisions, assumptions and trade offs made. 

The implementation must be done in a way that would allow easily making changes to the key parameters of the clustering algorithm implemented to be able to evaluate it against key metrics, select and document the most optimal configuration providing empirical evidence. 

The implementation must strictly adhere to creteria defined in T2 of the assignment brief (PhD_Multi_Resolution_Semantic_Abstraction_over_an_Evolving_Knowledge_1.md, not included in this repository). 

Any final representation produced by the algorithm must adjere to P1, P2 and P3 createria defined in the assignment brief. 

The fixtures produced by the method have to pass implemented validation described in 6a, the implemented method needs to be simple, well-controlled and defencible as described in What we're looking for in the assignment brief. 

Work only with the information available in the graph export (semantic, structural), don't use abstracts or paper text.

Take into account conclusions from notebooks/01_describe_graph.ipynb, notebooks/02_semantic_signal.ipynb and notebooks/03_structural_signal.ipynb when making design choices. 

The source code produced must be clean, concise, as simple as possible but satisfying implementation creteria, self-contained (no external references to anything outside tkh/), parametrised so that the configuration can be varied to run improvement experiments

The implementation is only considered done when
1. A formal statment is defined and documented describing the method and its optimisation objective in the formal statement (now docs/report.md §2) (update if exists)
2. An implementation of the method in python is done in tkh/ 
3. An implementation of a suitable null model that can be compared against the real model on the evaluation metrics complements the implementation
4. When the implemented model is run on the input data provided producing graph representation that fullfilts P1, P2 and P3 creteira 
5. When the output representation is validated by the implemented validator to confirm desired output structure