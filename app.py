# app.py
def process_csv(map_name):
    df = pd.read_csv(f'data/{map_name}.csv', parse_dates=['Expiry_Date'])
    current_time = datetime.now(pytz.utc)
    df['time_left'] = df['Expiry_Date'].apply(
        lambda x: (x - current_time).total_seconds() / 3600
    )
    df[['pos_x', 'pos_y']] = df['centre_coordinates'].str.extract(
        '\(([\d.]+),([\d.]+)\)'
    ).astype(float)
    return df.to_dict('records')
