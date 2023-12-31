# CS502-Project: Extending Few-Shot Learning Benchmark with RelationNet model

This repository is coding part of the Few-Shot Learning benchmark for the Biomedical datasets, developed by [Brbic Lab](https://brbiclab.epfl.ch/) and extended by Marija Zelic and Elena Mrdja with Relation Network algorithm. `README.md` has been mainly taken from the [Brbic Lab](https://brbiclab.epfl.ch/) with modifications added for the specifics of the RelationNet model.

## Instalation  

For successful running of our benchmark locally, first clone this repository.  

### Conda

Create a conda environment and install it with following command:

```bash
conda env create -f environment.yml 
```

Before each run, activate the environment with:

```bash
conda activate few-shot-benchmark 
```

### Pip

Alternatively, for environments that do not support
conda (e.g. Google Colab), install requirements with:

```bash
python -m pip install -r requirements.txt
```  

## Usage

### Training  

For the hyperparameter tuning of the RelationNet model for the specific problem and dataset, first go to the `hyperparameter_tuning.py`. Inside `if __name__ == '__main__':` function change parameters n_way, n_suport, n_query and dataset name (`swissprot` or `tabula_muris`) according to your problem and then run following command:  

```bash
python hyperparameter_tuning.py
```  
By default, hyperparameter tuning is set to the Swiss-Prot dataset, 5-way, 5-shot, 15-query problem. It is also important to keep line `wandb.log({"loss": avg_loss / float(i + 1)})` in the `meta_template.py`'s `train_loop()` function commented, during this execution. To perform more coarser grid search, add necessary parameters to the respective lists in the `hyperparameter_tuning()` function in the `hyperparameter_tuning.py` file. 

The training process will automatically evaluate at the end. To only evaluate without
running training, use the following:

```bash
python run.py exp.name={exp_name} method=maml dataset=tabula_muris
```

By default, method is set to MAML, and dataset is set to Tabula Muris.
The experiment name must always be specified.  

### Testing

The training process will automatically evaluate at the end. To only evaluate without
running training, use the following:

```bash
python run.py exp.name={exp_name} method=maml dataset=tabula_muris mode=test
```

Run `run.py` with the same parameters as the training run, with `mode=test` and it will automatically use the
best checkpoint (as measured by val ACC) from the most recent training run with that combination of
exp.name/method/dataset/model. To choose a run conducted at a different time (i.e. not the latest), pass in the timestamp
in the form `checkpoint.time="'yyyymmdd_hhmmss'"` To choose a model from a specific epoch, use `checkpoint.iter=40`. 

## Datasets  

The data itself is not in the GitHub, but will either be automatically downloaded
(Tabula Muris), or needs to be manually downloaded from [here](d) 
for the SwissProt dataset. These should be unzipped and put under `data/{dataset_name}`.  

The configurations for each dataset are located at `conf/dataset/{dataset_name}.yaml`.
To create a dataset, subclass the `FewShotDataset` class to create a SimpleDataset (for baseline / transfer-learning methods) and 
SetDataset (for the few-shot setting) and create a new config file for the dataset with the pointer to these classes.

The provided datasets are:

| Dataset      | Task                             | Modality         | Type           | Source                                                                 |
|--------------|----------------------------------|------------------|----------------|------------------------------------------------------------------------|
| Tabula Muris | Cell-type prediction             | Gene expression  | Classification | [Cao et al. (2021)](https://arxiv.org/abs/2007.07375)                  |
| SwissProt    | Protein function prediction      | Protein sequence | Classification | [Uniprot](https://www.uniprot.org/) |

## Methods

We provide a set of methods in `methods/`, including a baseline method that does typical transfer
learning, and meta-learning methods like Protoypical Networks (protonet), Matching Networks (matchingnet),
and Model-Agnostic Meta-Learning (MAML). To create a new method, subclass the `MetaTemplate` class and
create a new method config file at `conf/method/{method_name}.yaml` with the pointer to the new class.


The provided methods include:

| Method      | Source                             | 
|--------------|----------------------------------|
| Baseline, Baseline++ | [Chen et al. (2019)](https://arxiv.org/pdf/1904.04232.pdf) |
| ProtoNet | [Snell et al. (2017)](https://proceedings.neurips.cc/paper_files/paper/2017/file/cb8da6767461f2812ae4290eac7cbc42-Paper.pdf) |
| MatchingNet | [Vinyals et al. (2016)](https://proceedings.neurips.cc/paper/2016/file/90e1357833654983612fb05e3ec9148c-Paper.pdf) |
| MAML | [Finn et al. (2017)](https://proceedings.mlr.press/v70/finn17a/finn17a.pdf) |
| RelationNet | [Sung et al. (2018)](https://openaccess.thecvf.com/content_cvpr_2018/papers/Sung_Learning_to_Compare_CVPR_2018_paper.pdf)|


## Models

We provide a set of backbone layers, blocks, and models in `backbone.py`, inclduing a 2-layer fully connected network as
well as ConvNets and ResNets. The default backbone for each dataset is set in each dataset's config file,
e.g. `dataset/tabula_muris.yaml`. For the RelationNet model, there is additional backbone structure for the relation module specified in the method's config file `method/relationnet.yaml`

## Configurations

This repository uses the [Hydra](https://github.com/facebookresearch/hydra) framework for configuration management. 
The top-level configurations are specified in the `conf/main.yaml` file. Dataset-specific values are set in files in
the `conf/dataset/` directory, and few-shot method-specific files are specified in `conf/method`. 

Note that the files in the dataset directory are at the top-level package, so configurations can be set at the command
line directly, e.g. `n_shot = 5` or `backbone.layer_dim = [20,20]`. However, configurations in `conf/method` are in 
the method package, which needs to be specified e.g. `method.stop_epoch=20`. 

Note also that in Hydra, configurations are inherited through the specification of `defaults`. For instance, 
`conf/method/maml.yaml` inherits from `conf/method/meta_base.yaml`, which itself inherits from 
`conf/method/method_base.yaml`. Each configuration file then only needs to specify the deltas/differences
to the file it is inheriting from.

For more on Hydra, see [their tutorial](https://hydra.cc/docs/intro/). For an example of a benchmark that uses Hydra
for configuration management, see [BenchMD](https://github.com/rajpurkarlab/BenchMD).

## Experiment Tracking

We use [Weights and Biases](https://wandb.ai/) (WandB) for tracking experiments and results during training. 
All hydra configurations, as well as training loss, validation accuracy, and post-train eval results are logged.
To disable WandB, use `wandb.mode=disabled`. 

You must update the `project` and `entity` fields in `conf/main.yaml` to your own project and entity after creating one on WandB.

To log in to WandB, run `wandb login` and enter the API key provided on the website for your account.

## References
Algorithm implementations based on [COMET](https://github.com/snap-stanford/comet) and [CloserLookFewShot](https://github.com/wyharveychen/CloserLookFewShot). Dataset
preprocessing code is modified from each respective dataset paper, where applicable.
