import os
import pandas as pd
import numpy as np
from dash import Dash, dcc, html, dash_table
import plotly.express as px

# ========================
# 0. Перевірка робочої теки
# ========================
print("Поточна директорія:", os.getcwd())
print("Файли в директорії:", os.listdir())

# ======================================================================
# 1. Завантаження CSV-файлів
# ======================================================================
fact = pd.read_csv('Transactions_Fact.csv')
print(">>> [DEBUG] fact read:", fact.shape)
date_dim = pd.read_csv('Date_Dimension.csv')
regions = pd.read_csv('Region_Dimension.csv')
customers = pd.read_csv('Customer_Dimension.csv')
# trans_types = pd.read_csv('TransType_Dimension.csv')  # якщо потрібно

# ======================================================================
# 2. Зменшення даних (для швидшого відображення)
# ======================================================================
fact = fact.sample(100000, random_state=42)
print(">>> [DEBUG] fact після sample:", fact.shape)

# ======================================================================
# 3. Об’єднання даних (merge), якщо треба
# ======================================================================
if 'Year' not in fact.columns or 'Month' not in fact.columns:
    fact = fact.merge(date_dim[['Date_Key', 'Year', 'Month']], on='Date_Key', how='left')
    print(">>> [DEBUG] After merge з date_dim:", fact.shape)

if 'Region_ID' not in fact.columns:
    fact = fact.merge(customers[['Customer_ID', 'Region_ID']], on='Customer_ID', how='left')
    print(">>> [DEBUG] After merge з customers:", fact.shape)
else:
    if 'Region_ID_x' in fact.columns:
        fact = fact.rename(columns={'Region_ID_x': 'Region_ID'})
    if 'Region_ID_y' in fact.columns:
        fact.drop('Region_ID_y', axis=1, inplace=True)

if 'Region_Name' not in fact.columns:
    fact = fact.merge(regions[['Region_ID', 'Region_Name']], on='Region_ID', how='left')
    print(">>> [DEBUG] After merge з regions:", fact.shape)
else:
    print(">>> [DEBUG] Стовпець 'Region_Name' вже існує у fact.")

print(">>> [DEBUG] Final fact shape:", fact.shape)
print(fact.head(3))

if fact.shape[0] == 0:
    print("!!! [ERROR] fact порожній, графіки не відобразяться!")
else:
    print(">>> [DEBUG] fact має дані, продовжуємо.")

# ======================================================================
# 4. KPI
# ======================================================================
total_amount = fact['Amount'].sum()
avg_amount = fact['Amount'].mean()
total_fee = fact['Transaction_Fee'].sum()
num_transactions = fact.shape[0]

# ======================================================================
# 5. Побудова 4 різних графіків
# ======================================================================
# 5.1. Стовпчиковий графік (Сума транзакцій по роках)
df_year = fact.groupby('Year')['Amount'].sum().reset_index()
bar_year = px.bar(
    df_year, x='Year', y='Amount',
    title='Сума транзакцій по роках',
    labels={'Year': 'Рік', 'Amount': 'Сума транзакцій'}
)

# 5.2. Лінійний графік (Транзакції по місяцях, 2021)
selected_year = 2021
df_month = fact[fact['Year'] == selected_year].groupby('Month')['Amount'].sum().reset_index()
line_month = px.line(
    df_month, x='Month', y='Amount', markers=True,
    title=f'Транзакції по місяцях ({selected_year} рік)'
)

# 5.3. Кругова діаграма (Online/Offline)
df_type = fact.groupby('Trans_Type')['Amount'].sum().reset_index()
pie_type = px.pie(
    df_type, names='Trans_Type', values='Amount',
    title='Розподіл транзакцій за типами'
)

# 5.4. Гістограма (Розподіл сум транзакцій)
hist_amount = px.histogram(
    fact, x='Amount',
    title='Розподіл сум транзакцій',
    labels={'Amount': 'Сума транзакції'}
)


# ======================================================================
# 6. Створення ASCII sparkline замість HTML
# ======================================================================
def create_ascii_sparkline(vals, max_len=20):
    """
    Повертає коротку "ASCII Sparkline" зі символами ▁▂▃▄▅▆▇█
    Підходить, якщо не хочемо вбудовувати HTML/js чи kaleido.
    max_len: обмежує довжину (кількість символів).
    """
    blocks = "▁▂▃▄▅▆▇█"  # від меншої до більшої "висоти"
    n_blocks = len(blocks)

    if not isinstance(vals, list) or len(vals) == 0:
        return ""
    data = vals
    # Якщо дуже довгий список - зменшуємо для показу
    if len(data) > max_len:
        step = len(data) / max_len
        # вибираємо приблизно max_len точок
        indices = [int(i * step) for i in range(max_len)]
        data = [vals[i] for i in indices]

    mn = min(data)
    mx = max(data)
    rng = mx - mn
    if rng == 0:
        # всі однакові
        return "█" * len(data)

    spark = []
    for val in data:
        # нормалізуємо 0..1
        norm = (val - mn) / rng
        idx = int(norm * (n_blocks - 1))
        spark.append(blocks[idx])
    return "".join(spark)


# ======================================================================
# 7. Формування даних для таблиці
# ======================================================================
df_region_trend = fact.groupby(['Region_Name', 'Month'])['Amount'].sum().reset_index()
df_region_kpi = fact.groupby('Region_Name')['Amount'].agg(['sum', 'mean', 'count']).reset_index()

spark_data = df_region_trend.groupby('Region_Name')['Amount'].apply(list).reset_index()
spark_data.columns = ['Region_Name', 'Trend']

df_region_kpi = pd.merge(df_region_kpi, spark_data, on='Region_Name', how='left')
df_region_kpi['Sparkline'] = df_region_kpi['Trend'].apply(create_ascii_sparkline)

# Перетворення list -> str
table_data = df_region_kpi.to_dict('records')
for rec in table_data:
    for k, v in rec.items():
        if isinstance(v, list):
            rec[k] = str(v)

# ======================================================================
# 8. Dash layout
# ======================================================================
app = Dash(__name__)
server = app.server

app.layout = html.Div([
    html.H1("Бізнес-аналітична система для бізнесмена", style={
        'textAlign': 'center', 'padding': '10px', 'fontSize': '30px'
    }),

    # KPI
    html.Div([
        html.Div([
            html.H3("Загальна сума транзакцій"),
            html.P(f"{total_amount:,.2f}", style={'fontSize': '24px', 'color': '#34495E'})
        ], style={'width': '24%', 'display': 'inline-block', 'padding': '10px'}),
        html.Div([
            html.H3("Середня сума транзакцій"),
            html.P(f"{avg_amount:,.2f}", style={'fontSize': '24px', 'color': '#34495E'})
        ], style={'width': '24%', 'display': 'inline-block', 'padding': '10px'}),
        html.Div([
            html.H3("Загальна комісія"),
            html.P(f"{total_fee:,.2f}", style={'fontSize': '24px', 'color': '#34495E'})
        ], style={'width': '24%', 'display': 'inline-block', 'padding': '10px'}),
        html.Div([
            html.H3("Кількість транзакцій"),
            html.P(f"{num_transactions:,}", style={'fontSize': '24px', 'color': '#34495E'})
        ], style={'width': '24%', 'display': 'inline-block', 'padding': '10px'}),
    ], style={'backgroundColor': '#F0F0F0', 'marginBottom': '20px'}),

    # 4 графіки
    html.Div([
        html.Div([
            dcc.Graph(figure=bar_year, style={'height': '400px'})
        ], style={'width': '48%', 'display': 'inline-block', 'padding': '10px'}),
        html.Div([
            dcc.Graph(figure=line_month, style={'height': '400px'})
        ], style={'width': '48%', 'display': 'inline-block', 'padding': '10px'})
    ]),
    html.Div([
        html.Div([
            dcc.Graph(figure=pie_type, style={'height': '400px'})
        ], style={'width': '48%', 'display': 'inline-block', 'padding': '10px'}),
        html.Div([
            dcc.Graph(figure=hist_amount, style={'height': '400px'})
        ], style={'width': '48%', 'display': 'inline-block', 'padding': '10px'})
    ], style={'marginBottom': '20px'}),

    # Таблиця з ASCII sparkline
    html.H2("Региональний аналіз з трендами (ASCII sparkline)", style={'textAlign': 'center'}),
    dash_table.DataTable(
        id='region-table',
        columns=[
            {"name": "Регіон", "id": "Region_Name"},
            {"name": "Сума транзакцій", "id": "sum", "type": "numeric", "format": {"specifier": ",.2f"}},
            {"name": "Середня сума", "id": "mean", "type": "numeric", "format": {"specifier": ",.2f"}},
            {"name": "Кількість транзакцій", "id": "count", "type": "numeric"},
            {"name": "Тренд", "id": "Sparkline"}  # ASCII символи
        ],
        data=table_data,
        style_table={'overflowX': 'auto', 'maxWidth': '100%'},
        style_cell={'textAlign': 'center', 'whiteSpace': 'normal', 'height': 'auto'},
    )
], style={'maxWidth': '1200px', 'margin': '0 auto', 'fontFamily': 'sans-serif'})

if __name__ == '__main__':
    app.run(debug=True)
