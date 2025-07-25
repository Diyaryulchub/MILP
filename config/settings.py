﻿# config/settings.py

# Горизонт планирования
horizon_days   = 15            # начальный горизонт в днях (1…8)
hours_per_day  = 24            # число шагов в дне

days           = list(range(1, horizon_days + 1))
horizon_hours  = horizon_days * hours_per_day
hours          = list(range(1, horizon_hours + 1))

# Определение кампаний и ресурсов
campaigns  = ['K1','K2','K3','K4','K5','K6']

rolling1   = ['Resource1','Resource2']
rolling2   = ['Resource21','Resource22']
rolling3   = ['Resource31']
rolling4 = ['Resource41']

# Гибкая структура стадий → агрегаты
# теперь, вместо трёх отдельных списков,
# можно итерироваться по stage_aggs[stage]
stage_aggs = {
    1: rolling1,
    2: rolling2,
    3: rolling3,
    4: rolling4,
}

# Нормативно-справочная информация (НСИ) для выплавки (этап 1)
nsi_schedule = {
    1: ('K1', 700),
    2: ('K2', 300),
    3: ('K3', 400),
    4: ('K6', 1200),
    5: ('K4', 200),
    6: ('K5', 600),
}
# Справочные суммарные объёмы по выплавке
total_nsi = {k: 0 for k in campaigns}
for d, (k, v) in nsi_schedule.items():
    total_nsi[k] += v

# Производительность (тонн/день)
prod_rate = {
    ('Resource1','K1'): 133, ('Resource1','K2'): 254,
    ('Resource1','K3'): 100, ('Resource1','K4'): 375,
    ('Resource1','K5'): 300, ('Resource1','K6'): 553,

    ('Resource2','K1'): 100, ('Resource2','K2'): 100,
    ('Resource2','K3'): 100, ('Resource2','K4'): 100,
    ('Resource2','K5'): 300, ('Resource2','K6'): 300,
    
    ('Resource21','K1'):100, ('Resource21','K2'):100,
    ('Resource21','K3'):100, ('Resource21','K4'):100,
    ('Resource21','K5'):300, ('Resource21','K6'):300,
    ('Resource22','K1'):100, ('Resource22','K2'):100,
    ('Resource22','K3'):100, ('Resource22','K4'):100,
    ('Resource22','K5'):300, ('Resource22','K6'):300,
    ('Resource31','K1'):100, ('Resource31','K2'):150,
    ('Resource31','K3'):200, ('Resource31','K4'):200,
    ('Resource31','K5'):200, ('Resource31','K6'):300,
    ('Resource41','K1'):100, ('Resource41','K2'):150,
    ('Resource41','K3'):200, ('Resource41','K4'):200,
    ('Resource41','K5'):200, ('Resource41','K6'):300,
}

# Время охлаждения между этапами (дней)
cooling_time = {'K1':1,'K2':1,'K3':1,'K4':1,'K5':1,'K6':1}

# Время переналадки между кампаниями (в часах)
reconf_matrix = {
    'Resource2':   { (k1,k2):24 for k1 in campaigns for k2 in campaigns if k1!=k2 },
    'Resource1':   { (k1,k2):24 for k1 in campaigns for k2 in campaigns if k1!=k2 },
    'Resource21':  { (k1,k2):24 for k1 in campaigns for k2 in campaigns if k1!=k2 },
    'Resource22':  { (k1,k2):24 for k1 in campaigns for k2 in campaigns if k1!=k2 },
    'Resource31':  { (k1,k2):24 for k1 in campaigns for k2 in campaigns if k1!=k2 },
    'Resource41':  { (k1,k2):24 for k1 in campaigns for k2 in campaigns if k1!=k2 },
}
# Альтернатива
'''
reconf_matrix = {
    'Resource1': {
        ('K1', 'K2'): 8,  ('K1', 'K3'): 12, ('K1', 'K4'): 14, ('K1', 'K5'): 16, ('K1', 'K6'): 10,
        ('K2', 'K1'): 6,  ('K2', 'K3'): 9,  ('K2', 'K4'): 11, ('K2', 'K5'): 13, ('K2', 'K6'): 7,
        ('K3', 'K1'): 12, ('K3', 'K2'): 8,  ('K3', 'K4'): 10, ('K3', 'K5'): 14, ('K3', 'K6'): 9,
        ('K4', 'K1'): 10, ('K4', 'K2'): 10, ('K4', 'K3'): 11, ('K4', 'K5'): 12, ('K4', 'K6'): 8,
        ('K5', 'K1'): 15, ('K5', 'K2'): 14, ('K5', 'K3'): 13, ('K5', 'K4'): 12, ('K5', 'K6'): 11,
        ('K6', 'K1'): 9,  ('K6', 'K2'): 7,  ('K6', 'K3'): 8,  ('K6', 'K4'): 9,  ('K6', 'K5'): 10,
    },
    'Resource21': {
        ('K1', 'K2'): 10, ('K1', 'K3'): 11, ('K1', 'K4'): 12, ('K1', 'K5'): 13, ('K1', 'K6'): 14,
        ('K2', 'K1'): 9,  ('K2', 'K3'): 8,  ('K2', 'K4'): 10, ('K2', 'K5'): 11, ('K2', 'K6'): 12,
        ('K3', 'K1'): 7,  ('K3', 'K2'): 9,  ('K3', 'K4'): 11, ('K3', 'K5'): 13, ('K3', 'K6'): 15,
        ('K4', 'K1'): 8,  ('K4', 'K2'): 8,  ('K4', 'K3'): 8,  ('K4', 'K5'): 9,  ('K4', 'K6'): 10,
        ('K5', 'K1'): 10, ('K5', 'K2'): 9,  ('K5', 'K3'): 8,  ('K5', 'K4'): 7,  ('K5', 'K6'): 6,
        ('K6', 'K1'): 12, ('K6', 'K2'): 11, ('K6', 'K3'): 10, ('K6', 'K4'): 9,  ('K6', 'K5'): 8,
    },
    'Resource22': {
        ('K1', 'K2'): 6,  ('K1', 'K3'): 6,  ('K1', 'K4'): 6,  ('K1', 'K5'): 6,  ('K1', 'K6'): 6,
        ('K2', 'K1'): 6,  ('K2', 'K3'): 6,  ('K2', 'K4'): 6,  ('K2', 'K5'): 6,  ('K2', 'K6'): 6,
        ('K3', 'K1'): 6,  ('K3', 'K2'): 6,  ('K3', 'K4'): 6,  ('K3', 'K5'): 6,  ('K3', 'K6'): 6,
        ('K4', 'K1'): 6,  ('K4', 'K2'): 6,  ('K4', 'K3'): 6,  ('K4', 'K5'): 6,  ('K4', 'K6'): 6,
        ('K5', 'K1'): 6,  ('K5', 'K2'): 6,  ('K5', 'K3'): 6,  ('K5', 'K4'): 6,  ('K5', 'K6'): 6,
        ('K6', 'K1'): 6,  ('K6', 'K2'): 6,  ('K6', 'K3'): 6,  ('K6', 'K4'): 6,  ('K6', 'K5'): 6,
    },
    'Resource31': {
        ('K1', 'K2'): 15, ('K1', 'K3'): 15, ('K1', 'K4'): 15, ('K1', 'K5'): 15, ('K1', 'K6'): 15,
        ('K2', 'K1'): 15, ('K2', 'K3'): 15, ('K2', 'K4'): 15, ('K2', 'K5'): 15, ('K2', 'K6'): 15,
        ('K3', 'K1'): 15, ('K3', 'K2'): 15, ('K3', 'K4'): 15, ('K3', 'K5'): 15, ('K3', 'K6'): 15,
        ('K4', 'K1'): 15, ('K4', 'K2'): 15, ('K4', 'K3'): 15, ('K4', 'K5'): 15, ('K4', 'K6'): 15,
        ('K5', 'K1'): 15, ('K5', 'K2'): 15, ('K5', 'K3'): 15, ('K5', 'K4'): 15, ('K5', 'K6'): 15,
        ('K6', 'K1'): 15, ('K6', 'K2'): 15, ('K6', 'K3'): 15, ('K6', 'K4'): 15, ('K6', 'K5'): 15,
    }
}
'''
# Дни ремонтов: запрещено работать на агрегате r в день t
repairs = {
    'Resource2':   [],
    'Resource1':   [],
    'Resource21':  [],
    'Resource22':  [],
    'Resource31':  [],
    'Resource41':  []
}

# Штрафной множитель за переналадку в целевой функции
pen_reconf = 5.0
# Штрафной множитель за использование агрегата
pen_resource = 2.0

# can_parallel = True  → можно параллелить одну и ту же кампанию
can_parallel: dict[str, bool] = {
    'Resource2':  True,
    'Resource1':  True,
    'Resource21': True,
    'Resource22': True,
    'Resource31': True,
    'Resource41': True,
}