import sys
import os
import numpy as np
import torch
import logging
sys.path.insert(0, '../../')
sys.path.insert(0, '../')

import detectron2.utils.comm as comm
from detectron2.utils.logger import setup_logger, log_every_n_seconds
from detectron2.engine import default_argument_parser, default_setup, launch
from detectron2.config import get_cfg
from detectron2.evaluation import DatasetEvaluators, DatasetEvaluator, inference_on_dataset, print_csv_format, inference_context
from detectron2.checkpoint import DetectionCheckpointer

from segmentationsg.engine import ObjectDetectorTrainerWithCoco
from segmentationsg.data import add_dataset_config, VisualGenomeTrainData, register_datasets
from detectron2.data.datasets import register_coco_instances
from segmentationsg.modeling import *
parser = default_argument_parser()

def register_coco_data(args):
    annotations = args.DATASETS.MSCOCO.ANNOTATIONS
    dataroot = args.DATASETS.MSCOCO.DATAROOT
    register_coco_instances("coco_train_2017", {}, annotations + 'instances_train2017.json', dataroot + '/train2017/')
    register_coco_instances("coco_val_2017", {}, annotations + 'instances_val2017.json', dataroot + '/val2017/')

def setup(args):
    cfg = get_cfg()
    add_dataset_config(cfg)
    cfg.merge_from_file(args.config_file)
    cfg.merge_from_list(args.opts)
    cfg.freeze()
    register_datasets(cfg)
    register_coco_data(cfg)
    default_setup(cfg, args)
    setup_logger(output=cfg.OUTPUT_DIR, distributed_rank=comm.get_rank(), name="LSDA")
    return cfg

def main(args):
    cfg = setup(args)
    if args.eval_only:
        model = ObjectDetectorTrainerWithCoco.build_model(cfg)
        DetectionCheckpointer(model, save_dir=cfg.OUTPUT_DIR).resume_or_load(
            cfg.MODEL.WEIGHTS, resume=args.resume
        )
        res = ObjectDetectorTrainerWithCoco.test(cfg, model)
        if comm.is_main_process():
            verify_results(cfg, res)
        return res
    trainer = ObjectDetectorTrainerWithCoco(cfg)
    trainer.resume_or_load(resume=args.resume)
    return trainer.train()

if __name__ == '__main__':
    args = parser.parse_args()
    try:
        # use the last 4 numbers in the job id as the id
        default_port = os.environ['SLURM_JOB_ID']
        default_port = default_port[-4:]

        # all ports should be in the 10k+ range
        default_port = int(default_port) + 15000

    except Exception:
        default_port = 59482
    
    args.dist_url = 'tcp://127.0.0.1:'+str(default_port)
    print (args)
    
    launch(
        main,
        args.num_gpus,
        num_machines=args.num_machines,
        machine_rank=args.machine_rank,
        dist_url=args.dist_url,
        args=(args,),
    )
