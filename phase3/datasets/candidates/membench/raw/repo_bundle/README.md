<h1 align="center"> MemBench: Towards More Comprehensive Evaluation on the Memory of LLM-based Agents </h1>

<div align="center">

[![Paper](https://img.shields.io/badge/Paper-arXiv-b31b1b.svg?logo=arxiv)](https://arxiv.org/abs/2506.21605)
[![License](https://img.shields.io/badge/LICENSE-MIT-green.svg)](https://opensource.org/licenses/MIT)


Data location:

https://pan.baidu.com/s/1HqwY0nu5bltSAJ2TbnxcFQ?pwd=yzsj Extraction code: yzsj

or

https://drive.google.com/file/d/112Zraj4pTPH4Idph6i1uMOLA_LPFdGr0/view?usp=sharing

If you want to directly use the data sampled in the paper, you can find the 0-10k and 100k datasets in the **data2test** directory. These represent the lengths of the entire conversation. Note that if your test setup is to mimic the **memory flow**, you can use these directly. However, if you want to test the model's ability with **long contexts**, you should sample more examples.

## Data Details

We provide two versions of the data: **Categorical data** and  **data**.

**Categorical data** represents data for each category under the first-person (Participation) and third-person (Observation), with category information and details available in Appendix Table 6.

The **data** represents the full datasets after categorization, as mentioned in the paper, including:

- Participation-Reflective (FirstAgentHighLevel)
- Participation-Factual (FirstAgentLowLevel)
- Observation-Reflective (ThirdAgentHighLevel)
- Observation-Factual (ThirdAgentLowLevel)

## Noise data

We also provide a noise dataset, NoiseData, to extend the length of dialogues or information flows, including:

- FirstNoise (FirstAgent)
- ThirdNoise (ThirdAgent)

You can use `makenoise.py` to generate extended and sampled Complete Data. You can modify the main function in the source code to implement this. For each additional unit of noise length, the token count increases by about 1k on average.

You can refer to the following code:

```python
MakeNoiseMessageHighLevel('data/ThirdAgentDataHighLevel.json', 'data2test', length=10, sample_num=100)  ## Add noise to the third-person high-level

MakeNoiseMessage('data/ThirdAgentDataLowLevel.json', 'data2test', length=10, sample_num=100)  ## Add noise to the third-person low-level

MakeNoiseSession('data/FirstAgentDataLowLevel.json', 'data2test', length=10, sample_num=100)  ## Add noise to the first-person low-level

MakeNoiseSession('data/FirstAgentDataHighLevel.json', 'data2test', length=10, sample_num=100)  ## Add noise to the first-person high-level
```






