import difflib
import json


def get_dishes_by_category_merged(menu_data, category_name, similarity_threshold=0):
    """
    根据分类名称搜索并返回该分类下的所有菜品和价格，小类合并到父级分类中
    :param menu_data: 完整的菜单数据
    :param category_name: 要搜索的分类名称
    :param similarity_threshold: 相似度阈值，默认0.6
    :return: 匹配分类的菜品列表，按匹配度排序，小类已合并
    """
    matches = []  # 存储匹配结果

    def traverse_category(category, parent_name='', full_path='', parent_category=None,max_similarity=0):
        # 构建完整路径
        current_full_path = f"{parent_name} > {category.get('nameCn', '')}" if parent_name else category.get('nameCn',
                                                                                                             '')

        # 计算与目标分类名称的相似度
        name_variants = [
            category.get('nameCn', ''),
            category.get('topName', ''),
            current_full_path
        ]


        best_match_name = ''

        for name in name_variants:

            if name:
                name=name.replace('BBN', '')

                similarity = difflib.SequenceMatcher(None,  name.lower(),category_name.lower()).ratio()
                # print(name,category_name,similarity)

                if similarity > max_similarity:

                    max_similarity = similarity


                    best_match_name = name

        # 检查分类是否显示且有售卖商品
        has_items = has_selling_items(category) or has_selling_child_items(category)

        if category.get('showFlag') == '1' and has_items:
            # 如果是顶级分类（没有父级），创建新的匹配项
            if parent_category is None:
                match_info = {
                    'category_name': category.get('nameCn', ''),
                    'top_name': category.get('topName', ''),
                    'full_path': current_full_path,
                    'classId': category.get('classId'),
                    'similarity': max_similarity,
                    'dishes': [],
                    'dish_count': 0,
                    'sub_categories': []  # 记录包含的子分类
                }

                # 收集当前分类和所有子分类的菜品
                all_dishes = collect_all_dishes(category)
                match_info['dishes'] = all_dishes
                match_info['dish_count'] = len(all_dishes)

                # 记录包含的子分类名称
                sub_categories = get_sub_category_names(category)
                match_info['sub_categories'] = sub_categories

                matches.append(match_info)
            else:
                # 对于子分类，不单独创建匹配项，菜品会合并到父级中
                pass

        # 递归搜索子分类，传递当前分类作为父级
        for child in category.get('childClassList', []):
            current_parent = category.get('nameCn', '')
            # 如果是顶级分类，传递自己作为父级；否则传递上一级的父级
            traverse_category(child, current_parent, current_full_path,
                              category if parent_category is None else parent_category,max_similarity=max_similarity)

    def has_selling_items(category):
        """检查分类是否有在售菜品"""
        for menu in category.get('menuList', []):
            if (menu.get('saleFlag') == 'Y' and
                    menu.get('disabledStatus') == '0' and
                    menu.get('invalidFlag', 0) == 0):
                return True
        return False

    def has_selling_child_items(category):
        """检查子分类是否有在售菜品"""
        for child in category.get('childClassList', []):
            if has_selling_items(child) or has_selling_child_items(child):
                return True
        return False

    def collect_all_dishes(category):
        """收集分类及其所有子分类的在售菜品"""
        dishes = []

        # 收集当前分类的菜品
        for menu in category.get('menuList', []):
            if (menu.get('saleFlag') == 'Y' and
                    menu.get('disabledStatus') == '0' and
                    menu.get('invalidFlag', 0) == 0):
                dish_info = create_dish_info(menu)
                dishes.append(dish_info)

        # 递归收集所有子分类的菜品
        for child in category.get('childClassList', []):
            child_dishes = collect_all_dishes(child)
            dishes.extend(child_dishes)

        # 按sort字段排序
        dishes.sort(key=lambda x: x['sort'])
        return dishes

    def get_sub_category_names(category):
        """获取所有子分类的名称"""
        sub_names = []

        for child in category.get('childClassList', []):
            if child.get('showFlag') == '1':
                sub_names.append(child.get('nameCn', ''))
                # 递归获取更深层级的子分类名称
                grand_children = get_sub_category_names(child)
                sub_names.extend(grand_children)

        return sub_names

    def create_dish_info(menu):
        """创建菜品信息"""
        dish_info = {
            'linkId': menu.get('linkId'),
            'name': menu.get('showNameCn', menu.get('nameCn', '')),
            'price': menu.get('price'),
            'priceInitial': menu.get('priceInitial'),
            'menuFlag': menu.get('menuFlag'),
            'sort': int(menu.get('sort', 999)),
            'description': menu.get('descCn', ''),
            'abbrDesc': menu.get('abbrDesc', '')
        }

        # 处理价格显示
        if dish_info['priceInitial'] and dish_info['priceInitial'] != dish_info['price']:
            dish_info[
                'price_display'] = f"{int(dish_info['price']) / 100:.2f}元 (原价:{int(dish_info['priceInitial']) / 100:.2f}元)"
        else:
            dish_info['price_display'] = f"{int(dish_info['price']) / 100:.2f}元"

        return dish_info

    # 开始搜索
    for category in menu_data:
        traverse_category(category)

    # 按相似度排序，优先返回匹配度最高的
    matches.sort(key=lambda x: x['similarity'], reverse=True)

    # 过滤掉相似度低于阈值的匹配
    filtered_matches = [match for match in matches if match['similarity'] >= similarity_threshold]

    return filtered_matches


def get_best_match_dishes_merged(menu_data, category_name):
    """
    获取最佳匹配分类的菜品（小类已合并到父级）
    :param menu_data: 完整的菜单数据
    :param category_name: 要搜索的分类名称
    :return: 最佳匹配分类的菜品信息，如果没有匹配返回None
    """
    all_matches = get_dishes_by_category_merged(menu_data, category_name)

    if not all_matches:
        return None

    # 返回匹配度最高的分类
    best_match = all_matches[0]

    # 构建更简洁的返回结果
    result = {
        'matched_category': best_match['category_name'],
        'top_name': best_match['top_name'],
        'full_path': best_match['full_path'],
        'similarity_score': round(best_match['similarity'], 3),
        'total_dishes': best_match['dish_count'],
        'sub_categories_included': best_match['sub_categories'],
        'dishes': best_match['dishes']
    }

    return result
def handle_data(data,category_name):
    menu_data = data['data']['menuData']
    result=""
    best_match = get_best_match_dishes_merged(menu_data, category_name)
    if best_match:
        result = f"最佳匹配: {best_match['matched_category']}\n"
        result += f"包含子分类: {', '.join(best_match['sub_categories_included'])}\n"
        result += f"总菜品数量: {best_match['total_dishes']}\n"
        for dish in best_match['dishes']:
            result += f"  - {dish['name']}: {dish['price_display']}\n"
    else:
        result="没有匹配的菜品"
    return result

# 使用示例
if __name__ == "__main__":
    # 假设你的JSON数据已经加载
    with open('1.json', 'r', encoding='utf-8') as f:
        data = json.load(f)

    res=handle_data(data,'原味鸡')
    print(res)
    print("合并小类的分类搜索函数定义完成")