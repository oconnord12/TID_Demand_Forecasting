

import pandas as pd
import numpy as np







def check_missing_hourly_intervals(df):
    #convert idx to dt
    df.index = pd.to_datetime(df.index, utc=True)

    #create full indexed hourly time 
    full_time_index = pd.date_range(start=df.index.min(), end=df.index.max(), freq='H', tz='UTC')
    df_reindexed = df.reindex(full_time_index)

    #id missing hours
    missing_timestamps = df_reindexed[df_reindexed.isna().any(axis=1)]

    #sum missing hours/day
    daily_missing = missing_timestamps.resample('D').size()

    return daily_missing.sort_values(ascending=False)
	
def prepare_data_nn(df, look_back, pred_forward, model='nn', train=0.80, val=0.10, test=0.10):
    
    #convert to np
    df_as_np = df.to_numpy()
    
    #store X and y
    X = []
    y = []
    
    #iterate thru all possible values that satisfy a look back and prediction forward period
    for i in range(len(df_as_np) - look_back - pred_forward):
        
        #each row contains features from the i value to i to lookback, the series of X's and y's that will pred the coming y 
        row = [r for r in df_as_np[i:i+look_back]]
        X.append(row)
        
        #y values start as the value after the row, and continue to the pred forward (i.e. 24hr prediction etc)
        y_values = df_as_np[i + look_back + pred_forward - 1][0]
        y.append(y_values)
    
    #convert to array
    X = np.array(X)
    y = np.array(y)
    
    length = len(X)
    
    #split into train,test,split
    x_train , y_train = X[:int((train*length))], y[:int((train*length))]
    x_val, y_val = X[int((train*length)):int((train+val)*length)], y[int((train*length)):int((train+val)*length)]
    x_test, y_test = X[-int(test*length):], y[-int(test*length):]
    
    
    
    return x_train, y_train, x_val, y_val, x_test, y_test
    