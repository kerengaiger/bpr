import os
import gzip
import json
import math
import random
import pickle
import pprint
import argparse

import numpy as np
import pandas as pd


class DatasetLoader(object):
    def load(self):
        """Minimum condition for dataset:
          * All users must have at least one item record.
          * All items must have at least one user record.
        """
        raise NotImplementedError


class MovieLens1M(DatasetLoader):
    def __init__(self, data_dir, file_name):
        self.fpath = os.path.join(data_dir, file_name)
        self.pos_thresh = 4.0
        self.min_usr_len = 1
        self.max_usr_len = 60
        self.min_item_cnt = 10
        self.max_item_cnt = 10000
        self.fin_min_usr_len = 3

    def process_data(self, df):
        df = df[df['rate'] > self.pos_thresh]
        df = filter_by_cnt(df, 'user', self.min_usr_len, self.max_usr_len)
        df = filter_by_cnt(df, 'item', self.min_item_cnt, self.max_item_cnt)
        df = filter_by_cnt(df, 'user', self.fin_min_usr_len, self.max_usr_len)
        return df

    def load(self):
        df = pd.read_csv(self.fpath,
                         sep='::',
                         engine='python',
                         names=['user', 'item', 'rate', 'time'])
        df = self.process_data(df)
        return df


class Yahoo(DatasetLoader):
    def __init__(self, data_dir, file_name):
        self.fpath = os.path.join(data_dir, file_name)
        self.fin_min_usr_len = 3
        self.max_usr_len = 200

    def load(self):
        df = pd.read_csv(self.fpath, names=['user', 'item', 'rate', 'time'])
        df = filter_by_cnt(df, 'user', self.fin_min_usr_len, self.max_usr_len)
        return df


class MovieLens20M(DatasetLoader):
    def __init__(self, data_dir):
        self.fpath = os.path.join(data_dir, 'ratings.csv')

    def load(self):
        df = pd.read_csv(self.fpath,
                         sep=',',
                         names=['user', 'item', 'rate', 'time'],
                         usecols=['user', 'item', 'time'],
                         skiprows=1)
        return df


class AmazonBeauty(DatasetLoader):
    def __init__(self, data_dir, file_name='All_Beauty.json.gz'):
        self.fpath = os.path.join(data_dir, file_name)

    def load(self):
        raw_list = []
        with gzip.open(self.fpath) as f:
            for idx, line in enumerate(f):
                raw_data = json.loads(line)
                raw_list.append({'user': raw_data['reviewerID'],
                                 'item': raw_data['asin'],
                                 'rate': raw_data['overall'],
                                 'time': raw_data['unixReviewTime']})
        df = pd.DataFrame(raw_list)
        print('Check if any column has null value')
        print(df.isnull().any())
        print('Total user number: %d' % df['user'].nunique())
        print('Total item number: %d' % df['item'].nunique())
        print('The number of unique item per user')
        print(df.groupby('user')['item'].nunique().value_counts())
        print('The number of unique user per item')
        print(df.groupby('item')['user'].nunique().value_counts())
        return df


class Gowalla(DatasetLoader):
    """Work In Progress"""
    def __init__(self, data_dir):
        self.fpath = os.path.join(data_dir, 'loc-gowalla_totalCheckins.txt')

    def load(self):
        df = pd.read_csv(self.fpath,
                         sep='\t',
                         names=['user', 'time', 'latitude', 'longitude', 'item'],
                         usecols=['user', 'item', 'time'])
        df_size, df_nxt_size = 0, len(df)
        while df_size != df_nxt_size:
            # Update
            df_size = df_nxt_size

            # Remove user which doesn't contain at least five items to guarantee the existance of `test_item`
            groupby_user = df.groupby('user')['item'].nunique()
            valid_user = groupby_user.index[groupby_user >= 15].tolist()
            df = df[df['user'].isin(valid_user)]
            df = df.reset_index(drop=True)

            # Remove item which doesn't contain at least five users
            groupby_item = df.groupby('item')['user'].nunique()
            valid_item = groupby_item.index[groupby_item >= 15].tolist()
            df = df[df['item'].isin(valid_item)]
            df = df.reset_index(drop=True)

            # Update
            df_nxt_size = len(df)

        print('User distribution')
        print(df.groupby('user')['item'].nunique().describe())
        print('Item distribution')
        print(df.groupby('item')['user'].nunique().describe())
        return df


def convert_unique_idx(df, column_name):
    print(len(df[column_name].unique()))
    column_dict = {x: i for i, x in enumerate(df[column_name].unique())}
    df[column_name] = df[column_name].apply(column_dict.get)
    df[column_name] = df[column_name].astype('int')
    assert df[column_name].min() == 0
    assert df[column_name].max() == len(column_dict) - 1
    return df, column_dict


def create_user_list(df, user_size):
    user_list = [list() for u in range(user_size)]
    for row in df.itertuples():
        user_list[row.user].append((row.time, row.item))
    return user_list


def split_train_test(df, user_size, test_size=0.2, time_order=False):
    """Split a dataset into `train_user_list` and `test_user_list`.
    Because it needs `user_list` for splitting dataset as `time_order` is set,
    Returning `user_list` data structure will be a good choice."""
    # TODO: Handle duplicated items
    if not time_order:
        test_idx = np.random.choice(len(df), size=int(len(df)*test_size))
        train_idx = list(set(range(len(df))) - set(test_idx))
        test_df = df.loc[test_idx].reset_index(drop=True)
        train_df = df.loc[train_idx].reset_index(drop=True)
        test_user_list = create_user_list(test_df, user_size)
        train_user_list = create_user_list(train_df, user_size)
    else:
        total_user_list = create_user_list(df, user_size)
        train_user_list = [None] * len(total_user_list)
        test_user_list = [None] * len(total_user_list)
        for user, item_list in enumerate(total_user_list):
            # Choose latest item
            item_list = sorted(item_list, key=lambda x: x[0])
            # Split item
            if int(test_size) != 0:
                # in this case we chose an absolute number for test items
                test_item = item_list[-int(test_size):]
                item_list = item_list[:-int(test_size)]
                valid_item = item_list[-int(test_size):]
                train_item = item_list[:-int(test_size)]
            else:
                test_item = item_list[math.ceil(len(item_list)*(1-test_size)):]
                train_item = item_list[:math.ceil(len(item_list)*(1-test_size))]
            # Register to each user list
            test_user_list[user] = test_item
            train_user_list[user] = train_item
    # Remove time
    test_user_list = [list(map(lambda x: x[1], l)) for l in test_user_list]
    train_user_list = [list(map(lambda x: x[1], l)) for l in train_user_list]
    return train_user_list, test_user_list


def create_pair(user_list):
    pair = []
    for user, item_list in enumerate(user_list):
        pair.extend([(user, item) for item in item_list])
    return pair


def filter_by_cnt(df, col, min_cnt, max_cnt):
    return df.groupby(col).filter(lambda x: (len(x) > min_cnt) and len(x) < max_cnt)


def main(args):
    if args.dataset == 'ml-1m':
        df = MovieLens1M(args.data_dir, 'ratings.dat').load()
    elif args.dataset == 'ml-20m':
        df = MovieLens20M(args.data_dir).load()
    elif args.dataset == 'amazon-beauty':
        df = AmazonBeauty(args.data_dir).load()
    elif args.dataset == 'yahoo':
        df = Yahoo(args.data_dir, 'yahoo_full_ranks.csv').load()
    else:
        raise NotImplementedError
    df, user_mapping = convert_unique_idx(df, 'user')
    df, item_mapping = convert_unique_idx(df, 'item')
    print('Complete assigning unique index to user and item')

    user_size = len(df['user'].unique())
    item_size = len(df['item'].unique())

    train_user_list, test_user_list = split_train_test(df,
                                                       user_size,
                                                       test_size=args.test_size,
                                                       time_order=args.time_order)
    print('Complete spliting items for training and testing')

    train_pair = create_pair(train_user_list)
    print('Complete creating pair')

    dataset = {'user_size': user_size, 'item_size': item_size, 
               'user_mapping': user_mapping, 'item_mapping': item_mapping,
               'train_user_list': train_user_list, 'test_user_list': test_user_list,
               'train_pair': train_pair}
    dirname = os.path.dirname(os.path.abspath(args.output_data))
    os.makedirs(dirname, exist_ok=True)
    with open(args.output_data, 'wb') as f:
        pickle.dump(dataset, f, protocol=pickle.HIGHEST_PROTOCOL)


if __name__ == '__main__':
    # Parse argument
    parser = argparse.ArgumentParser()
    parser.add_argument('--dataset',
                        choices=['ml-1m', 'ml-20m', 'amazon-beauty', 'gowalla', 'yahoo'])
    parser.add_argument('--data_dir',
                        type=str,
                        default=os.path.join('data', 'ml-1m'),
                        help="File path for raw data")
    parser.add_argument('--output_data',
                        type=str,
                        default=os.path.join('preprocessed', 'ml-1m.pickle'),
                        help="File path for preprocessed data")
    parser.add_argument('--test_size',
                        type=float,
                        default=1,
                        help="Proportion for training and testing split")
    parser.add_argument('--time_order',
                        action='store_true',
                        help="Proportion for training and testing split")
    args = parser.parse_args()
    main(args)
