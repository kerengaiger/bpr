import argparse
from collections import Counter


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data_dir', type=str, default='./data/', help="data directory path")
    parser.add_argument('--train_usrs', type=str, default='./data/corpus_avi.txt', help="corpus path")
    parser.add_argument('--test_usrs', type=str, default='./data/test_corpus_avi.txt', help="test corpus path")
    return parser.parse_args()


def main():
    args = parse_args()
    with open(args.train_usrs) as ftrain, open(args.test_usrs) as ftest:
        train_lsts = ftrain.readlines()
        test_lsts = ftest.readline()
    data = train_lsts + test_lsts
    users_cnt = len(data)
    print(f'Users count:{users_cnt}')

