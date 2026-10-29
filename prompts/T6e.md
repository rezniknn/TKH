Implement a minimal retrieval agent based on the constructed graph hierarchy to satisfy goals outlined in T6 Extrinsic Utility in the assignment brief (PhD_Multi_Resolution_Semantic_Abstraction_over_an_Evolving_Knowledge_1.md, not included in this repository). 

Implement evaluation code of the retrieval agent provided the ground truth in the format defined in data/questions.csv and data/ground_truth.json.

Implementation requirements:
1. Retrieval agent has to be able to understand questions of type A (specific search) and type B (synthesis of evidence)
2. Retrieval agent has to be able to correctly identify the right temporal snapshot to be used 
3. Retrieval agnent has to be able to perform semantic similarity match between a question and a semantic content of a graph's node to find the closest match at each hierarchy level 
4. Retrieval agent has to be able to find expected methods and required citations from the finest level nodes most closely matching the question semantically for type A questions and return the list in a format defined by ground truth 
5. Retrieval agent has to be able to find required claims and required citations from the finest level nodes most closely matching the question semantically for type B questions and return the list in a format defined by ground truth

The implementation is only considered done when:
1. A lightweight retrieval agent is built satisfying goals outlined in T6 Extrinsic Utility in the assignment brief and implementation requirements outlined above 
2. An evaluator is build allowing to run retrieval agent on a set of questions in a format defined in data/questions.csv comparing retrival results against ground truth ansers in a format defined in data/ground_truth.json and comparing retrieval agent's performance against flat baseline search scored on hit-rate and steps-to-target metrics 
3. An evaluator is run with the input data from the data/ folder and a report is produced outlining the results of the evaluation of the retrieval agent 
4. All design decisions and choices for both the retrival agent implementation and the evaluator implementation are documented and outlined in the evaluation report