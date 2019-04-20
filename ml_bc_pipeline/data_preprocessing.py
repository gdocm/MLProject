import sys
import numpy as np
from sklearn.impute import SimpleImputer
import pandas as pd
from scipy.stats import zscore,iqr
from sklearn.ensemble import IsolationForest
from sklearn import metrics
from scipy.stats import multivariate_normal
from sklearn.metrics.pairwise import euclidean_distances
#import eif as iso
from sklearn.cluster import DBSCAN
from sklearn.covariance import EllipticEnvelope
from sklearn.neighbors import LocalOutlierFactor
import statsmodels.api as sm
from sklearn import svm
from scipy.spatial.distance import cdist
from sklearn.preprocessing import MinMaxScaler
from sklearn.preprocessing import OneHotEncoder

class Processor:
    """ Performs data preprocessing

        The objective of this class is to preprocess the data based on training subset. The
        preprocessing steps focus on constant features removal, missing values treatment and
        outliers removal and imputation.

    """

    def __init__(self, training, unseen):
        """ Constructor

            It is worth to notice that both training and unseen are nothing more nothing less
            than pointers, i.e., pr.training is DF_train and pr.unseen is DF_unseen yields True.
            If you want them to be copies of respective objects, use .copy() on each parameter.

        """
        self.training = training #.copy() to mantain a copy of the object
        self.unseen = unseen #.copy() to mantain a copy of the object
        self.cat_vars = ['Education', 'Marital_Status', 'AcceptedCmp3', 'AcceptedCmp4', 'AcceptedCmp5',
                    'AcceptedCmp1', 'AcceptedCmp2', 'Complain', 'Response']
        #missing columns 'Income' 'num_days_customer'
        self.numerical_var = ['Year_Birth', 'Kidhome', 'Teenhome',  'Recency', 'MntWines',
                         'MntFruits', 'MntMeatProducts', 'MntFishProducts',
                         'MntSweetProducts', 'MntGoldProds', 'NumDealsPurchases', 'NumWebPurchases',
                         'NumCatalogPurchases', 'NumStorePurchases',
                         'NumWebVisitsMonth', 'Response']

        self._generate_dummies()

        #Deal with missing values
        self._drop_missing_values()

        #Outlier Treatment
        self._manual_outlier_removal()
        self._normalize()
        print("Preprocessing complete!")

    #DEALING WITH MISSING VALUES
    def _generate_dummies(self):
        features_to_enconde = ['Education', 'Marital_Status']

        columns = []
        idxs = []
        control = 0
        for column in features_to_enconde:
            for index in range(len(self.training[column].unique()) - 1):
                columns.append(column + '_' + self.training[column].unique()[index])
                idxs.append(control)
                control = control + 1
            control = control + 1

        # encode categorical features from training data as a one-hot numeric array.
        enc = OneHotEncoder(handle_unknown='ignore')
        Xtr_enc = enc.fit_transform(self.training[features_to_enconde]).toarray()
        # update training data
        df_temp = pd.DataFrame(Xtr_enc[:, idxs], index=self.training.index, columns=columns)
        self.training = pd.concat([self.training, df_temp], axis=1)
        for c in columns:
            self.training[c] = self.training[c].astype('category')
        # use the same encoder to transform unseen data
        Xun_enc = enc.transform(self.unseen[features_to_enconde]).toarray()
        # update unseen data
        df_temp = pd.DataFrame(Xun_enc[:, idxs], index=self.unseen.index, columns=columns)
        self.unseen = pd.concat([self.unseen, df_temp], axis=1)
        for c in columns:
            self.unseen[c] = self.unseen[c].astype('category')

    def _drop_missing_values(self):
        self.training.dropna(inplace=True)
        self.unseen.dropna(inplace=True)

    def _impute_num_missings_mean(self):
        ''' Imputes numerical features with the mean value and drops categorical missing values'''
        self._imputer = SimpleImputer(missing_values=np.nan, strategy='mean')
        X_train_imputed = self._imputer.fit_transform(self.training[self.numerical_var].values)
        X_unseen_imputed = self._imputer.transform(self.unseen[self.numerical_var].values)

        self.training[self.numerical_var] = X_train_imputed
        self.unseen[self.numerical_var] = X_unseen_imputed
        self.training[self.cat_vars].dropna(inplace=True)
        self.unseen[self.cat_vars].dropna(inplace=True)

    # DEALING WITH OUTLIERS
    ### UNIVARIATE OUTLIER DETECTION
    def _filter_df_by_std(self):
        '''Removes Outliers based on standard deviation'''
        def _filter_ser_by_std(series_, n_stdev=3.0):
            mean_, stdev_ = series_.mean(), series_.std()
            cutoff = stdev_ * n_stdev
            lower_bound, upper_bound = mean_ - cutoff, mean_ + cutoff
            return [True if i < lower_bound or i > upper_bound else False for i in series_]

        training_num = self.training[self.numerical_var].drop(["Response"], axis=1)
        mask = training_num.apply(axis=0, func=_filter_ser_by_std, n_stdev=3.0)
        training_num[mask] = np.NaN
        self.training[training_num.columns] = training_num

        return list(training_num.columns)

    def _manual_outlier_removal(self):

        #Ouliers were removed based on boxplot analysis as well as min max normalized data

        ds = self.training
        # Separating between numerical and categorical variables:
        num_ds = ds[self.numerical_var]
        #cat_ds = ds[self.cat_vars]

        # Year_birth
        ds = ds[(ds['Year_Birth'] > 1920)]

        # KidHome (no outliers)

        # TeenHome (no outliers)

        # Income
        ds = ds[ds['Income'] < 153920]

        # num_days_customer (no outliers)

        # MntWines (??? maybe no outliers)

        # MntFruits (??? maybe no outliers)

        # MntMeatProducts
        ds = ds[ds['MntMeatProducts'] < 1500]

        # MntFishProducts (??? maybe no outliers)

        # MntSweetProducts
        ds = ds[ds['MntSweetProducts'] < 250]

        # MntGoldProds
        ds = ds[ds['MntGoldProds'] < 290]

        # NumDealsPurchases
        ds = ds[ds['NumDealsPurchases'] < 14]  # 74 rows deleted

        # NumWebPurchases
        ds = ds[ds['NumWebPurchases'] < 23]  # 3 rows deleted

        # NumCatalogPurchases ???
        ds = ds[ds['NumCatalogPurchases'] < 21]

        # NumStorePurchases

        # NumWebVisitsMonth
        ds = ds[ds['NumWebVisitsMonth'] < 13]

    def _z_score_outlier_detection(self, treshold):
        ''' Only for numerical data'''

        zscores = zscore(self.training[self.numerical_var])
        #Count number of non outliers per line
        temp = np.sum((zscores < treshold) & (zscores > -treshold), axis=1)
        #If the number of outliers per line is equal to the columns of numerical
        #Keep line
        self.training = pd.DataFrame(self.training.values[temp == len(self.numerical_var),:],columns=self.training.columns)

        #data = self.training
        #df = pd.DataFrame(zscore(data[self.numerical_var]), columns=self.numerical_var)
        #df.index = data.index
        #temp = np.sum(df > treshold, axis=1)
        #my_outliers = temp[temp > 0].index
        #temp = np.sum(df < -treshold, axis=1)
        #my_outliers.append(temp[temp > 0].index)
        #return np.unique(my_outliers)

    def _boxplot_outlier_detection(self):
        zscores = zscore(self.training[self.numerical_var])
        iqr_ = iqr(zscores)
        #Count number of non outliers per line
        temp = np.sum(zscores < 1.5*iqr_, axis=1)
        #If the number of outliers per line is equal to the columns of numerical
        #Keep line
        self.training = pd.DataFrame(self.training.values[temp == len(self.numerical_var),:],columns=self.training.columns)
        '''
        box_plot_outliers = []
        ids = []
        for var in self.numerical_var:
            df = pd.Series(zscore(data[var]))
            df.index = data.index
            for record in df.index:
                #Should'nt we need to check if zscore is less then 1.5*iqr?
                if df[df.index == record].iloc[0] > 1.5 * iqr(df):
                    if record not in box_plot_outliers:
                        box_plot_outliers.append(record)
                else:
                    ids.append(record)

        self.training = self.training.iloc[set(ids)]
        return box_plot_outliers
        '''

    def Robust_z_score_method(self,df, treshold):
        #What is ds???
        ds = self.rm_df
        numerical = self.numerical_var
        df = df[numerical]
        med = df.median()
        MAD = [np.median(np.abs(ds[var] - ds[var].median())) for var in df]
        df = 0.6745 * (df - df.median()) / MAD
        pd.options.mode.use_inf_as_na = True
        df = df.fillna(0)

        def RZ_outliers():
            outliers = np.sum(df > treshold, axis=1)
            return outliers[outliers > 0].index

        return df, RZ_outliers()

    #### MULTIVARIATE OUTLIER DETECTION
    """ CONTAMINATION: The amount of contamination of the data set, i.e. the proportion of outliers in the data set. 
    Used when fitting to define the threshold on the decision function. """

    def isolation_forest(self, contamination):
        ds = self.training[self.numerical_var]
        clf = IsolationForest(max_samples=100, contamination=contamination, random_state=np.random.RandomState(42))
        clf.fit(ds)
        self.training = pd.DataFrame(self.training.values[clf.predict(ds) == 1,:],columns=self.training.columns)
        #outliers_isoflorest = pd.Series(outliers_isoflorest)
        #outliers_isoflorest.index = ds.index
        #return outliers_isoflorest[outliers_isoflorest == -1]

    ## CUIDADO AGAIN COM OS PARAMETROS
    # INSTALAR EIF NO PIP
    def extended_isolation_forest(self):
        #Do values need to be normalized
        ds = self.training
        if_eif = iso.iForest(norm_encoded_ds.values, ntrees=100, sample_size=256, ExtensionLevel=2)
        anomaly_scores = if_eif.compute_paths(X_in=norm_encoded_ds.values)
        anomaly_scores = pd.Series(anomaly_scores)
        anomaly_scores.index = norm_encoded_ds.index
        anomaly_scores.sort_values(ascending=False, inplace=True)
        return anomaly_scores


    # Getting the columns (variables) means
    def mahalanobis_distance_outlier(self):
        ds = self.training
        var_means = ds.mean(axis=0).values.reshape(1, -1)
        # Getting the inverse of the covariance matrix
        try:
            inv_cov_matrix = np.linalg.inv(np.cov(ds.T))
        except:
            m = np.cov(ds.T)
            i = np.eye(m.shape[0], m.shape[1])
            inv_cov_matrix = np.linalg.lstsq(m, i)[0]
        try:
            np.linalg.cholesky(inv_cov_matrix)
            print("all good")
        except:
            print("WARNING, mahalanobis no good..")
            # REVER ISTO...
        MDs = cdist(var_means, ds, 'mahalanobis', VI=inv_cov_matrix)
        MDs = pd.Series([distance for sublist in MDs for distance in sublist], index=ds.index)

        def find_outliers():
            treshold = 3.
            std = np.std(MDs)
            k = treshold * std
            m = np.mean(MDs)
            mahalanobis_outliers = []
            for index in MDs.index:
                if (MDs[index] >= m + k) or (MDs[index] <= m - k):
                    if index not in mahalanobis_outliers:
                        mahalanobis_outliers.append(index)  # index of the outlier
            return np.array(mahalanobis_outliers)

        return find_outliers()

    def Dbscan_outlier_detection(self, minpoints=None, radius=None):
        ds = self.training[self.numerical_var]
        outlier_detection = DBSCAN(
            eps=radius,
            metric="euclidean",
            min_samples=minpoints,
            n_jobs=-1)

        self.training = pd.DataFrame(self.training.values[outlier_detection.fit_predict(ds) != -1, :], columns=self.training.columns)
        # Seing the number of identified noise (outliers)
        #np.sum(clusters == -1)
        # Identifying the outliers:
        #clusters = pd.Series(clusters)
        #clusters.index = ds.index
        #return clusters.sort_values()


    def elliptic_envelope_out(self, contamination):
        ds = self.training[self.numerical_var]
        elliptic = EllipticEnvelope(contamination=contamination)
        elliptic.fit(ds)
        results = elliptic.predict(ds)
        self.training = pd.DataFrame(self.training.values[results == 1, :],columns=self.training.columns)
        #outlier_elliptic = pd.Series(results)
        #outlier_elliptic.index = ds.index
        #return outlier_elliptic[outlier_elliptic == -1]


    def local_outlier_factor(self, n_neighbors = None, contamination = None):
        ds = self.training[self.numerical_var]
        lof = LocalOutlierFactor(n_neighbors=10, contamination=0.1)
        outiler_lof = lof.fit_predict(ds)
        self.training = pd.DataFrame(self.training.values[outiler_lof == 1, :], columns=self.training.columns)
        #outiler_lof = pd.Series(outiler_lof)
        #outiler_lof.index = ds.index
        #return outiler_lof[outiler_lof == -1]

    def one_class_svm(self):
        ds = self.training[self.numerical_var]
        oneclasssvm = svm.OneClassSVM()
        oneclasssvm_outliers = oneclasssvm.fit_predict(ds)
        self.training = pd.DataFrame(self.training.values[oneclasssvm_outliers == 1, :], columns=self.training.columns)
        #oneclasssvm_outliers.index = ds.index
        #return oneclasssvm_outliers[oneclasssvm_outliers == -1]

    def cooks_distance_outlier(self, vd):
        df = self.training
        X = df[vd]
        Y = df.drop(columns=vd)
        m = sm.OLS(X, Y).fit()
        infl = m.get_influence()
        sm_fr = infl.summary_frame()
        return sm_fr['cooks_d'].sort_values(ascending=False)

    def outlier_rank(*arg):
        IDS = []
        for array in arg:
            IDS = [id_ for sublist in IDS for id_ in sublist]
        counts = [IDS.count(i) for i in IDS]
        return dict(zip(IDS, counts))

    ### NORMALIZATION
    def _normalize(self):
        dummies = list(self.training.select_dtypes(include=["category", "object"]).columns)
        dummies.append('Response')
        scaler = MinMaxScaler()
        scaler.fit(self.training[self.training.columns[~self.training.columns.isin(dummies)]].values)
        self.training[self.training.columns[~self.training.columns.isin(dummies)]] = pd.DataFrame(
            scaler.transform(self.training[self.training.columns[~self.training.columns.isin(dummies)]].values),
            columns=self.training[self.training.columns[~self.training.columns.isin(dummies)]].columns,
            index=self.training[self.training.columns[~self.training.columns.isin(dummies)]].index)
        self.unseen[self.unseen.columns[~self.unseen.columns.isin(dummies)]] = pd.DataFrame(
            scaler.transform(self.unseen[self.unseen.columns[~self.unseen.columns.isin(dummies)]].values),
            columns=self.unseen[self.unseen.columns[~self.unseen.columns.isin(dummies)]].columns,
            index=self.unseen[self.unseen.columns[~self.unseen.columns.isin(dummies)]].index)