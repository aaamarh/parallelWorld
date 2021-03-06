import json
import os
import pymysql
import re
import xlrd
from collections import OrderedDict
from flask import request, Flask, render_template, send_from_directory, url_for, redirect, url_for
from pyecharts import Pie, Line, Radar, Grid, Bar
from pyecharts_javascripthon.api import TRANSLATOR
from models import app, db, Charts, Msg
from werkzeug import secure_filename

REMOTE_HOST = "https://pyecharts.github.io/assets/js"
UPLOAD_FOLDER = '/uploads/data/'
app.config['UPLOAD_FOLDER'] = os.getcwd() + '/uploads/data/'
ALLOWED_EXTENSIONS = set(['xlsx'])

# app = Flask(__name__)
app.config['DEBUG'] = True


@app.route('/')
def home():
    _pie = pie_chart(w=260, h=240, is_show=False, is_toolbox_show=False)
    pie_javascript_snippet = TRANSLATOR.translate(_pie.options)
    _bar = bar_chart(w=220, h=220, is_show=False, is_toolbox_show=False)
    pie_javascript_snippet = TRANSLATOR.translate(_pie.options)

    return render_template(
        'home.html',
        host=REMOTE_HOST,
        script_list=_pie.get_js_dependencies(),
        # 渲染图表
        pie_chart=_pie.render_embed(),
        bar_chart=_bar.render_embed()
    )


@app.route("/index/", methods=['POST', 'GET'])
def index():
    _pie = pie_chart()
    pie_javascript_snippet = TRANSLATOR.translate(_pie.options)
    _line = line_chart()
    line_javascript_snippet = TRANSLATOR.translate(_line.options)
    _randar = radar_chart()
    randar_javascript_snippet = TRANSLATOR.translate(_randar.options)
    _bar = bar_chart()
    bar_javascript_snippet = TRANSLATOR.translate(_bar.options)

    # 从数据库读取数据信息渲染到chart
    is_show_chart = Charts.query.filter_by(is_show=True).first()
    chart_type = is_show_chart.name  # 图表类型：pie, line 等等
    current_chart = Charts.query.filter_by(name=chart_type).first()  #默认展示的图表
    current_chart_paras = current_chart.inf.all()

    # 获取所有的信息
    info = Msg.query.filter().all()

    # 将数据进行分别显示
    if request.method == 'GET' and request.args.get('opt') == "true":
        res = request.args
        info_value = res.get('info_value')
        info_name = res.get('info_name')

        chart_type = res.get('chart_type')  # 图表类型：pie, line 等等
        chart_formula = res.get('chart_formula')
        # 从数据库中选择所有数据
        data = Msg.query.filter_by(info_name=info_name).first()
        chart = Charts.query.filter_by(name=chart_type).first()
        chart.formula = chart_formula
        data.info_value = int(info_value)
        db.session.commit()

    if request.method == 'POST':
        # 保存文件
        file = request.files['file']
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            print(app.config['UPLOAD_FOLDER'])
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        #  再次连接数据库，对用户导入的 .sql 文件进行处理
        conn = pymysql.connect(host="10.163.66.147", port=3306,
                               user="root", password="root", database="demo1")
        cursor = conn.cursor()

        #  上传.sql 正则方法
        delete_sql = "SELECT CONCAT('drop table ',table_name,';') FROM information_schema.`TABLES` WHERE table_schema='demo1';"
        # db.session.execute(delete_sql)
        # delete_data = db.session.filter()
        cursor.execute(delete_sql)
        delete_data = cursor.fetchall()
        for delete_data1 in delete_data:
            for delete_data2 in delete_data1:
                db.session.execute(delete_data2)

        try:
            # 读取SQL文件,获得sql语句的list  此处位置可以为变量
            with open(app.config['UPLOAD_FOLDER'] + 'demo1.sql', 'r+') as f:
                sql_list = f.read().split(';')[:-1]  # sql文件最后一行加上;
                # 将每段sql里的换行符改成空格
                sql_list = [x.replace('\n', ' ')
                            if '\n' in x else x for x in sql_list]
            # 执行sql语句，使用循环执行sql语句
            print(sql_list)
            for sql_item in sql_list:
                # print(sql_item)
                if sql_item[0:4] == '  --':
                    reg = re.compile("([-| ]+)([\w| ]+)[-| ]*(.+)")  # 正则匹配公式
                    sql = reg.search(sql_item)
                    cursor.execute(sql.group(3))
                    conn.commit()
                    continue
                cursor.execute(sql_item + ';')
                conn.commit()

        except pymysql.Error as e:
            print(e)
        finally:
            conn.close()
        return redirect(url_for('index'))

    return render_template(
        "demo.html",
        host=REMOTE_HOST,
        script_list=_pie.get_js_dependencies(),
        
        info=info,
        chart_type=chart_type,
        current_chart=current_chart,
        current_chart_paras=current_chart_paras,
        # 渲染图表
        pie_chart=_pie.render_embed(),
        line_chart=_line.render_embed(),
        radar_chart=_randar.render_embed(),
        bar_chart=_bar.render_embed()
    )


@app.route('/show_data/')
def show_select():
    ''' 图表参数进行展示，隐藏 '''
    chart_type = request.args.get('chart_type')
    current_chart = Charts.query.filter_by(name=chart_type).first()  # 用户当前选择的图表
    # current_chart_paras = current_chart.inf.all()
    res = request.args
    check_data_id = res.get('checkId')
    if res.get('select') == 'true':
        current_chart.inf.append(Msg.query.get(check_data_id))
        db.session.add(current_chart)
        db.session.commit()
    elif res.get('select') == 'false':
        current_chart.inf.remove(Msg.query.get(check_data_id))
        # db.session.delete(current_chart)
        db.session.commit()
    return ''


@app.route('/set_chart/', methods=['GET'])
def set_chart():
    chart_type = request.args.get('chart_type')
    chart_tit = request.args.get('chart_tit')
    chart = Charts.query.filter_by(name=chart_type).first()
    chart.tit = chart_tit
    db.session.commit()
    data = {"chart_name": chart_tit, "chart_type": chart_type}
    return json.dumps(data)


@app.route('/chart_data/', methods=['GET'])
def chart_data():
    if request.method  == 'GET':
        selectChartType = request.args.get('selectChart')  # 图表类型：pie, line 等等
        currentChartType = request.args.get('currentChart')
        current_chart = Charts.query.filter_by(name=currentChartType).first()
        select_chart = Charts.query.filter_by(name=selectChartType).first()
        current_chart.is_show=False
        select_chart.is_show = True
        db.session.commit()
    return ''

## #####################################
# BEGIN 图表区
## #####################################


def pie_chart(w=600, h=400, is_show=True, is_toolbox_show=True):
    chart = Charts.query.filter_by(name='pie').first()
    current_chart_paras = chart.inf.all()

    pie = Pie(chart.tit, "", title_pos='center', width=w, height=h, title_color='#fff', title_text_size=12)

    attr = []
    v = []

    info = Msg.query.filter()
    for i in current_chart_paras:
        v.append(i.info_value)
        attr.append(i.info_name)

    # 获取JSON数据
    with open('map.json', 'r') as f:
        data = json.load(f)
        num_blue = data["blue"]
        num_red = data["red"]

    label_color = ['#bbd3b1', "#8db978", '#669f40', '#548534']

    # v = [num_red, num_blue]
    pie.add('', attr, v, legend_pos='right', legend_orient='vertical',
            legend_text_color='#fff', label_color=label_color, is_label_show=is_show, is_toolbox_show=is_toolbox_show)
    return pie


def line_chart():
    line = Line("伤亡趋势图", "伤亡人口", title_pos='center')
    attr = ["衬衫", "羊毛衫", "雪纺衫", "裤子", "高跟鞋", "袜子"]
    v1 = [5, 20, 36, 10, 10, 100]
    v2 = [55, 60, 16, 20, 15, 80]
    line = Line("折线图示例")
    visual_range_color = ['#313695', '#4575b4', '#74add1', '#abd9e9', '#e0f3f8',
                          '#ffffbf', '#fee090', '#fdae61', '#f46d43', '#d73027', '#a50026']
    line.add("牺牲", attr, v1, mark_point=[
             "average"], visual_range_color=visual_range_color, is_visualmap=True, visual_range=[0, 30])
    line.add("负伤", attr, v2, is_smooth=True, mark_line=[
             "max", "average"], legend_pos='right', legend_orient="vertical")
    return line


def bar_chart(w=600, h=400, is_show=True, is_toolbox_show=True):
    chart = Charts.query.filter_by(name='bar').first()
    current_chart_paras = chart.inf.all()
    o = []
    attr = ['军队规模']
    v = []

    bar = Bar("标记线和标记点示例",title_pos='center', width=w, height=h, title_color='#fff', title_text_size=12)
    # bar.add(legend_pos='right', legend_orient='vertical', label_text_color='#fff')
    label_color = ['#bbd3b1', "#8db978", '#669f40', '#548534']

    for i in current_chart_paras:
        bar.add(i.info_name, attr, [i.info_value], is_label_show=is_show, is_toolbox_show=is_toolbox_show,legend_pos= "80%", legend_orient='vertical',bar_category_gap=0)

    # bar.add("a", attr, [v[0]])
    # bar.add("商家B", attr, [v[1]])
    # bar.add("商家c", attr, [v[2]])
    # bar.add("商家d", attr, [v[3]])
    return bar


def radar_chart():
    schema = [
        ("销售", 6500), ("管理", 16000), ("信息技术", 30000),
        ("客服", 38000), ("研发", 52000), ("市场", 25000)
    ]
    v1 = [[4300, 10000, 28000, 35000, 50000, 19000]]
    v2 = [[5000, 14000, 28000, 31000, 42000, 21000]]
    radar = Radar()
    radar.config(schema)
    radar.add("预算分配", v1, is_splitline=True, is_axisline_show=True)
    radar.add("实际开销", v2, label_color=["#4e79a7"], is_area_show=False,
              legend_selectedmode='single')
    return radar

## #####################################
# END 图表区
## #####################################


@app.route("/calc/", methods=["POST", "GET"])
def calc():
    res = request.form.get('t')

    with open('map.json', 'r') as f:
        data = json.load(f)
    if res and type(res) == 'string':
        res = int(res)
    if not res:
        pass
    data["blue"] = res
    with open("map.json", 'w') as dump_f:
        json.dump(data, dump_f)

    return render_template(
        'calc.html',
        res=res
    )

#  这里是用来测试多个图表显示的页面  后期删掉


@app.route("/test/")
def test():
    attr = ["衬衫", "羊毛衫", "雪纺衫", "裤子", "高跟鞋", "袜子"]
    v1 = [5, 20, 36, 10, 75, 90]
    v2 = [10, 25, 8, 60, 20, 80]
    bar = Bar("柱状图示例", height=720)
    bar.add("商家A", attr, v1, is_stack=True)
    bar.add("商家B", attr, v2, is_stack=True)
    line = Line("折线图示例", title_top="50%")
    attr = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    line.add(
        "最高气温",
        attr,
        [11, 11, 15, 13, 12, 13, 10],
        mark_point=["max", "min"],
        mark_line=["average"],
    )
    line.add(
        "最低气温",
        attr,
        [1, -2, 2, 5, 3, 2, 0],
        mark_point=["max", "min"],
        mark_line=["average"],
        legend_top="50%",
    )

    grid = Grid()
    grid.add(bar, grid_bottom="60%")
    grid.add(line, grid_top="60%")

    grid_javascript_snippet = TRANSLATOR.translate(grid.options)
    return render_template(
        'test.html',
        host=REMOTE_HOST,
        # 饼状图
        grid_id=grid.chart_id,
        grid_renderer=grid.renderer,
        my_width=600,
        my_height=400,
        grid_custom_function=grid_javascript_snippet.function_snippet,
        grid_options=grid_javascript_snippet.option_snippet,
        script_list=grid.get_js_dependencies(),
    )


# def calculate():
#     res = request.form.get('t')
#     return res


@app.route('/uploads/<filename>')
def upload_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1] in ALLOWED_EXTENSIONS


@app.route('/threelib/<filename>')
def three_lib(filename):
    return send_from_directory('threelib/', filename)


@app.route('/js/<filename>')
def bootstrap_js(filename):
    return send_from_directory('bootstrap-3.3.7-dist/js/', filename)


@app.route('/static/<filename>')
def bootstrap_static(filename):
    return send_from_directory('bootstrap-3.3.7-dist/css/', filename)


@app.route('/index_static/<filename>')
def index_static(filename):
    return send_from_directory('static/css/', filename)


@app.route('/index_js/<filename>')
def index_js(filename):
    return send_from_directory('static/js/', filename)


if __name__ == '__main__':
    app.run()
