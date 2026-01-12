from app.models import get_db

# --- [修复] 将配置常量移出类定义，作为模块全局变量 ---
BASE_X = 80
BASE_Y = 80
BLOCK_W = 120
BLOCK_H = 70
GAP_X = 220  # 列间距
GAP_Y = 160  # 行间距


# --- [修复] 将辅助函数改为独立函数，不再依赖 MapService 类实例 ---
def _get_grid_pos(col, row):
    """计算网格绝对坐标"""
    return {
        'x': BASE_X + col * GAP_X,
        'y': BASE_Y + row * GAP_Y,
        'w': BLOCK_W,
        'h': BLOCK_H
    }


class MapService:
    """
    图书馆地图服务：数字孪生版
    采用严格网格系统布局 (Grid System Layout)
    Canvas Size: 1000 x 600
    Grid Unit: 160x120 (4 Columns x 3 Rows)
    """

    # 静态地图配置 (基于网格)
    # Col: 0-3, Row: 0-2
    SHELF_MAP = {
        # --- Floor 1: 人文社科 (矩阵排列) ---
        'A': {**_get_grid_pos(0, 0), 'floor': 1, 'name': 'A 马列主义', 'icon': 'fas fa-landmark'},
        'B': {**_get_grid_pos(1, 0), 'floor': 1, 'name': 'B 哲学宗教', 'icon': 'fas fa-brain'},
        'C': {**_get_grid_pos(2, 0), 'floor': 1, 'name': 'C 社会科学', 'icon': 'fas fa-users'},
        'D': {**_get_grid_pos(3, 0), 'floor': 1, 'name': 'D 政治法律', 'icon': 'fas fa-balance-scale'},

        'E': {**_get_grid_pos(0, 1), 'floor': 1, 'name': 'E 军事', 'icon': 'fas fa-fighter-jet'},
        'F': {**_get_grid_pos(1, 1), 'floor': 1, 'name': 'F 经济', 'icon': 'fas fa-chart-line', 'w': 340},  # 跨两列
        'G': {**_get_grid_pos(3, 1), 'floor': 1, 'name': 'G 文化教育', 'icon': 'fas fa-graduation-cap'},

        'H': {**_get_grid_pos(0, 2), 'floor': 1, 'name': 'H 语言文字', 'icon': 'fas fa-language'},
        'I': {**_get_grid_pos(1, 2), 'floor': 1, 'name': 'I 文学', 'icon': 'fas fa-feather-alt'},
        'J': {**_get_grid_pos(2, 2), 'floor': 1, 'name': 'J 艺术', 'icon': 'fas fa-palette'},
        'K': {**_get_grid_pos(3, 2), 'floor': 1, 'name': 'K 历史地理', 'icon': 'fas fa-globe-asia'},

        # --- Floor 2: 自然科学 (矩阵排列) ---
        'N': {**_get_grid_pos(0, 0), 'floor': 2, 'name': 'N 自然总论', 'icon': 'fas fa-atom'},
        'O': {**_get_grid_pos(1, 0), 'floor': 2, 'name': 'O 数理化', 'icon': 'fas fa-flask'},
        'P': {**_get_grid_pos(2, 0), 'floor': 2, 'name': 'P 天文地球', 'icon': 'fas fa-meteor'},
        'Q': {**_get_grid_pos(3, 0), 'floor': 2, 'name': 'Q 生物', 'icon': 'fas fa-dna'},

        'R': {**_get_grid_pos(0, 1), 'floor': 2, 'name': 'R 医药卫生', 'icon': 'fas fa-heartbeat'},
        'S': {**_get_grid_pos(1, 1), 'floor': 2, 'name': 'S 农业科学', 'icon': 'fas fa-seedling'},
        'T': {**_get_grid_pos(2, 1), 'floor': 2, 'name': 'T 工业技术', 'icon': 'fas fa-cogs', 'w': 340},  # 跨两列 T & U位置

        'U': {**_get_grid_pos(0, 2), 'floor': 2, 'name': 'U 交通运输', 'icon': 'fas fa-car'},
        'V': {**_get_grid_pos(1, 2), 'floor': 2, 'name': 'V 航空航天', 'icon': 'fas fa-space-shuttle'},
        'X': {**_get_grid_pos(2, 2), 'floor': 2, 'name': 'X 环境安全', 'icon': 'fas fa-leaf'},
        'Z': {**_get_grid_pos(3, 2), 'floor': 2, 'name': 'Z 综合性', 'icon': 'fas fa-book'},
    }

    @staticmethod
    def generate_call_number(isbn, clc_code, author):
        db = get_db()
        # 统计种次号
        count = db.execute("SELECT COUNT(*) FROM CIRCULATION_HEAD WHERE CLC_CODE = ?", (clc_code,)).fetchone()[0]
        sequence = count + 1

        # 作者号处理
        author_code = 'A'
        if author:
            try:
                first_char = author.strip()[0]
                if '\u4e00' <= first_char <= '\u9fff':
                    # 这里可以引入 pinyin 库，为了不引入额外依赖，简单处理
                    # 实际项目中建议：from pypinyin import pinyin, Style
                    author_code = 'Z'
                else:
                    author_code = first_char.upper()
            except:
                pass

        return f"{clc_code}/{author_code}-{sequence}"

    @staticmethod
    def get_map_data(target_isbn=None):
        db = get_db()

        # 1. 计算热力图
        stats = db.execute('''
            SELECT substr(CLC_CODE, 1, 1) as P, COUNT(*) as C 
            FROM CIRCULATION_HEAD 
            GROUP BY substr(CLC_CODE, 1, 1)
        ''').fetchall()
        heat_map = {row['P']: row['C'] for row in stats}

        # 归一化热力值 (0.0 - 1.0)
        max_val = max(heat_map.values()) if heat_map else 1

        zones = []
        target_zone_id = None
        target_floor = 1

        for prefix, config in MapService.SHELF_MAP.items():
            count = heat_map.get(prefix, 0)
            # 只有当count>0时才显示热力颜色
            intensity = count / max_val if max_val > 0 else 0

            zone_data = config.copy()
            zone_data['id'] = prefix
            zone_data['count'] = count
            zone_data['intensity'] = intensity
            zones.append(zone_data)

        if target_isbn:
            book = db.execute("SELECT CLC_CODE FROM CIRCULATION_HEAD WHERE ISBN=?", (target_isbn,)).fetchone()
            if book:
                clc = book['CLC_CODE']
                for prefix in sorted(MapService.SHELF_MAP.keys(), key=len, reverse=True):
                    if clc.startswith(prefix):
                        target_zone_id = prefix
                        target_floor = MapService.SHELF_MAP[prefix]['floor']
                        break

        return {
            'zones': zones,
            'target_zone_id': target_zone_id,
            'target_floor': target_floor,
            'total_stock': sum(heat_map.values())
        }