import sys
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split, StratifiedKFold, KFold
from ml_bc_pipeline.data_loader import Dataset
from ml_bc_pipeline.data_preprocessing import Processor
from ml_bc_pipeline.feature_engineering import FeatureEngineer
from ml_bc_pipeline.model import gradientBoosting,grid_search_MLP, assess_generalization_auroc, decision_tree, naive_bayes, logistic_regression, xgboost, ensemble, adaboost
from datetime import datetime
from os import listdir
import json
from sklearn.utils import class_weight


def main():

    # ===========================
    # PARAMETERS
    # ===========================

    seed = 1
    cv_splits = 5
    kfold_simple = True
    stratified_kfold=False

    test_version = len(listdir('Logs'))

    global log
    log = pd.DataFrame()

    global pipeline
    pipeline = {}

    def report(best_estimator_, test, best_params_ = None,model_name = "None", print_graph = False):
        auprc, stats = assess_generalization_auroc(best_estimator_, test, print_graph)
        stats['model_type'] = model_name
        stats['params'] = best_params_
        stats['auroc'] = auprc
        global log
        if log.shape[1] == 0:
            log = pd.DataFrame([stats.values()], columns = stats.keys())
        else:
            log = log.append(pd.DataFrame([stats.values()], columns = stats.keys()))
        print("AUROC: {:.2f}".format(auprc))

    def calculate_averages(variable_list):
        global log
        data = log
        models = data['model_type'].unique()
        columns_ = ['model'] + variable_list
        print(models)
        averages = pd.DataFrame()
        for model in models:
            var_averages = [model]
            for variable in variable_list:
                var_averages.append(np.average(data[data['model_type'] == model][variable]))
            if averages.shape[1] == 0:
                averages = pd.DataFrame([var_averages], columns=columns_)
            else:
                averages = averages.append(pd.DataFrame([var_averages], columns=columns_))
        return averages

    # +++++++++++++++++ 1) load and prepare the data
    ds = Dataset("ml_project1_data.xlsx").rm_df
    # +++++++++++++++++ 2) split into train and unseen
    DF_train, DF_unseen = train_test_split(ds.copy(), test_size=0.2, stratify=ds["Response"], random_state=seed)


    #class_weights = class_weight.compute_class_weight('balanced', np.unique(DF_train['Response']), DF_train['Response'])
    #class_weights

    #skf = StratifiedKFold(n_splits=cv_splits, shuffle=True)

    #for train_index, test_index in skf.split(DF_train[DF_train.columns!='Reponse'],DF_train['Response']):

    #train = DF_train.ix[train_index]
    #test = DF_train.ix[test_index]

    # +++++++++++++++++ 3) preprocess, based on train

    for seed in range(5):

        pr = Processor(DF_train, DF_unseen, seed)
        pipeline['preprocessing'] = pr.report

        # +++++++++++++++++ 4) feature engineering
        fe = FeatureEngineer(pr.training, pr.unseen)
        pipeline['feature_engineering'] = fe.report

        # =====================================
        # NEURAL NETWORK
        # =====================================

        mlp_param_grid = {'mlpc__hidden_layer_sizes': [(3), (6), (3, 3), (5, 5)],
                          'mlpc__learning_rate_init': [0.001, 0.01]}

        mlp_gscv = grid_search_MLP(pr.training, mlp_param_grid, seed)
        print("Best parameter set: ", mlp_gscv.best_params_)
        #report(mlp_gscv.best_estimator_, fe.unseeen, mlp_gscv.best_params_, grid_search_MLP.__name__)

        # =====================================
        # DECISION TREE
        # =====================================

        dt_param_grid = {'dt__criterion': ["entropy", "gini"],
                         'dt__max_features': [3, 5, 7, None],
                         "dt__max_depth": [3, 4, 5, 6],
                         "dt__min_samples_split": [30, 50, 70]}
        dt_gscv = decision_tree(pr.training, dt_param_grid, seed)
        print("Best parameter set: ", dt_gscv.best_params_)
        #report(dt_gscv.best_estimator_, fe.unseeen, dt_gscv.best_params_,decision_tree.__name__)

        # =====================================
        # NAIVE BAYES
        # =====================================

        nb_param_grid = {'nb__alpha': [0, 0.25, 0.5, 0.75, 1]}  # i'm not sure about this parameter
        nb_gscv = naive_bayes(pr.training, nb_param_grid)
        print("Best parameter set: ", nb_gscv.best_params_)
        #report(nb_gscv.best_estimator_, fe.unseeen, nb_gscv.best_params_,naive_bayes.__name__)

        # =====================================
        # LOGISTIC REGRESSION
        # =====================================

        logr_param_grid = {'lr__penalty': ['l1', 'l2'],
                           'lr__C': np.logspace(-4, 4, 20),
                           'lr__solver': ['liblinear']}
        logr_gscv = logistic_regression(pr.training, logr_param_grid, seed)
        print("Best parameter set: ", logr_gscv.best_params_)
        #report(logr_gscv.best_estimator_, fe.unseeen, logr_gscv.best_params_,logistic_regression.__name__)

        # =====================================
        # XGBOOST
        # =====================================

        xgb = xgboost(fe.training, seed)
        report(xgb, fe.unseen, model_name=xgboost.__name__)

        # =====================================
        # ADABOOST
        # =====================================

        adaboost_ = adaboost(fe.training, seed)
        report(adaboost_, fe.unseen, model_name='adaboost')

        # =====================================
        # GRADIENTBOOSTING
        # =====================================

        gradientboost_ = gradientBoosting(fe.training, seed)
        report(gradientboost_, fe.unseen, model_name='gradientboost')

        # =====================================
        # ENSEMBLE
        # =====================================

        classifiers = {
            'neural_net': mlp_gscv.best_estimator_,
            'dt': dt_gscv.best_estimator_,
            'nb': nb_gscv.best_estimator_,
            'logr': logr_gscv.best_estimator_,
        }

        ensemble_estimator = ensemble(fe.training, classifiers)
        report(ensemble_estimator, fe.unseen, classifiers.keys(), ensemble.__name__)


        if kfold_simple:
            skf = KFold(n_splits=cv_splits, shuffle=True)
        elif stratified_kfold:
            skf = StratifiedKFold(n_splits=cv_splits, shuffle=True)


        for train_index, test_index in skf.split(DF_train.loc[:, DF_train.columns != "Response"],DF_train['Response']):

            train = DF_train.ix[train_index]
            test = DF_train.ix[test_index]

            pr = Processor(train, test, seed)
            pipeline['preprocessing'] = pr.report

            # +++++++++++++++++ 4) feature engineering
            fe = FeatureEngineer(pr.training, pr.unseen)
            pipeline['feature_engineering'] = fe.report

            # =====================================
            # NEURAL NETWORK
            # =====================================

            mlp_gscv.best_estimator_ = mlp_gscv.best_estimator_.fit(fe.training.loc[:, fe.training.columns != "Response"].values, fe.training["Response"].values)
            #print("Best parameter set: ", mlp_gscv.best_params_)
            report(mlp_gscv.best_estimator_, fe.unseen, mlp_gscv.best_params_, grid_search_MLP.__name__)

            # =====================================
            # DECISION TREE
            # =====================================

            dt_gscv.best_estimator_ = dt_gscv.best_estimator_.fit(fe.training.loc[:, fe.training.columns != "Response"].values, fe.training["Response"].values)
            #print("Best parameter set: ", dt_gscv.best_params_)
            report(dt_gscv.best_estimator_, fe.unseen, dt_gscv.best_params_,decision_tree.__name__)

            # =====================================
            # NAIVE BAYES
            # =====================================

            nb_gscv.best_estimator_ = nb_gscv.best_estimator_.fit(fe.training.loc[:, fe.training.columns != "Response"].values, fe.training["Response"].values)
            #print("Best parameter set: ", nb_gscv.best_params_)
            report(nb_gscv.best_estimator_, fe.unseen, nb_gscv.best_params_,naive_bayes.__name__)

            # =====================================
            # LOGISTIC REGRESSION
            # =====================================

            logr_gscv.best_estimator_ = logr_gscv.best_estimator_.fit(fe.training.loc[:, fe.training.columns != "Response"].values, fe.training["Response"].values)
            #print("Best parameter set: ", logr_gscv.best_params_)
            report(logr_gscv.best_estimator_, fe.unseen, logr_gscv.best_params_,logistic_regression.__name__)

            # =====================================
            # XGBOOST
            # =====================================

            xgb = xgb.fit(fe.training.loc[:, fe.training.columns != "Response"].values, fe.training["Response"].values)
            report(xgb, fe.unseen, model_name=xgboost.__name__)

            # =====================================
            # ADABOOST
            # =====================================

            adaboost_ = adaboost_.fit(fe.training.loc[:, fe.training.columns != "Response"].values, fe.training["Response"].values)
            report(adaboost_, fe.unseen, model_name='adaboost')

            # =====================================
            # GRADIENTBOOSTING
            # =====================================

            gradientboost_ = gradientboost_.fit(fe.training.loc[:, fe.training.columns != "Response"].values, fe.training["Response"].values)
            report(gradientboost_, fe.unseen, model_name='gradientboost')

            # =====================================
            # ENSEMBLE
            # =====================================

            ensemble_estimator = ensemble_estimator.fit(fe.training.loc[:, fe.training.columns != "Response"].values, fe.training["Response"].values)
            report(ensemble_estimator, fe.unseen, classifiers.keys(), model_name='ensemble')



        log.to_csv('Logs/' + 'version' + str(test_version)+'_'+str(seed)+'.csv')
        with open('Pipelines/version'+str(test_version)+'_'+str(seed)+'.txt', 'w') as file:
            file.write(json.dumps(pipeline))

        averages = calculate_averages(['auroc','precision','recall','f1_score','best_threshold', 'best_profit'])
        averages.to_csv('Averages/version' + str(test_version) +'_'+str(seed)+'.csv')

if __name__ == "__main__":
    main()

