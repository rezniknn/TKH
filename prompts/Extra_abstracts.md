Implement an additional evaluation of the semantic coherence of the hierarchies produced by the implemented method using downloaded paper abstracts and evaluating average cross-paper semantic proximity of abstracts from papers attributed to the same super-node on the coarsest level in the hierarchy vs papers attributed to different super-nodes. 

Run the evaluation on the latest snapshot only.

Implementation must be done in eval/extra folder.

Download and store paper abstracts in plain text files in the same folder to be used by the evaluator if not already downloaded.

Use an open source LLM to evaluate pairwise semantic closenes of each paper pair. Cache LLM call results to be used offline. Use offline LLM cashe as a default unless it does not exist.

Split average pairwise semantic closeness by paper pairs attributed to the same coarsest level super node vs pairs where each paper is attributed to two different super-nodes. 

Create a short evaluation report presenting evaluation comparison and conclusions about semantic coherence of super nodes based on the evaluation method.