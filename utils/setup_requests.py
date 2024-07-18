import os
from pymongo import MongoClient
import pandas as pd
import streamlit as st
from bson import ObjectId
import unicodedata
import random
import re
from utils.util_tools import from_html_to_text

#função setup conteudo de aula e questão quiz
def get_df(collection_name,colunas):    
    try:
        server=os.environ["SERVER_TYPE"]
        user_alx=os.environ["MONGO_ALEXANDRIA_USERNAME"]
        pwd_alx=os.environ["MONGO_ALEXANDRIA_PASSWORD"]
        port_alx=os.environ["MONGO_ALEXANDRIA_HOST"]
        clt_alx="alexandria-kroton"
        str_conn = f"{server}://{user_alx}:{pwd_alx}@{port_alx}"
        client = MongoClient(str_conn)
        db = client[clt_alx]
    except:
        st.error(body='Erro ao conectar com o alexandria',icon='🚨')
    
    lista_rows=[]
    collection = db[collection_name]
    query = collection.find()
    for x in query:
        filtered_row = {key: x.get(key) for key in colunas}
        lista_rows.append(filtered_row)
    df=pd.DataFrame(lista_rows)
    return df

def cursos_dict():
    cursos={
        'Pedagogia':['PENSAMENTO CIENTÍFICO','PRÁTICAS PEDAGÓGICAS: IDENTIDADE DOCENTE​','FUNCIONAMENTO DA EDUCAÇÃO BRASILEIRA E POLÍTICAS PÚBLICAS​','FUNDAMENTOS DA EDUCAÇÃO​','PSICOLOGIA DA EDUCAÇÃO E DA APRENDIZAGEM'],
        'Administração':['MATEMÁTICA FINANCEIRA','LEGISLAÇÃO EMPRESARIAL APLICADA','ANÁLISE DE CUSTOS​','MÉTODOS QUANTITATIVOS​','OPTATIVA I (EDUCAÇÃO AMBIENTAL;GESTÃO DO CONHECIMENTO)​'],
        'Gestão em RH':['MATEMÁTICA FINANCEIRA','LEGISLAÇÃO EMPRESARIAL APLICADA','GESTÃO DE PESSOAS​','MÉTODOS QUANTITATIVOS​','OPTATIVA  II (AVALIAÇÃO DE PERFORMANCE; COMUNICAÇÃO E EDUCAÇÃO CORPORATIVA; LIBRAS - LÍNGUA BRASILEIRA DE SINAIS)​','PROJETO INTEGRADO INOVAÇÃO - GESTÃO​'],
        'Desenvolvimento de Sistemas':['ENGENHARIA DE SOFTWARE​','LINGUAGEM DE PROGRAMAÇÃO​','LÓGICA E MATEMÁTICA COMPUTACIONAL','ALGORITMOS E PROGRAMAÇÃO ESTRUTURADA​','ANÁLISE E MODELAGEM DE SISTEMAS​','PROJETO INTEGRADO INOVAÇÃO - ANÁLISE E DESENVOLVIMENTO DE SISTEMAS​'],
        'Serviço Social':['INTRODUÇÃO À FILOSOFIA​','ESTATÍSTICA E INDICADORES SOCIAIS​','ADMINISTRAÇÃO E PLANEJAMENTO DE SERVIÇO SOCIAL​','LEGISLAÇÃO SOCIAL E DIREITOS HUMANOS​','ECONOMIA POLÍTICA​'],
        'Perícia Criminal':['FUNDAMENTOS HISTÓRICOS E INTRODUÇÃO AO ESTUDO DO DIREITO','FUNDAMENTOS DE INVESTIGAÇÃO E CRIMINALÍSTICA​','TEORIA GERAL DO PROCESSO​','EXPANSÃO DA CRIMINALIDADE​','TEORIA GERAL DO DIREITO CONSTITUCIONAL','PROJETO INTEGRADO INOVAÇÃO - INVESTIGAÇÃO E PERÍCIA CRIMINAL​'],
        'Questoes com Imagem':['Pedagogia','Administração','Gestão em RH','Desenvolvimento de Sistemas','Serviço Social','Perícia Criminal']
    }
    return cursos

@st.cache_data 
def questao_com_imagem(materia):
    banco_questoes={
        'Pedagogia':[ObjectId('65a85d5580efedfc5dde6a30'), ObjectId('65a18b217e88b6381ac88a22')],
        'Administração':[ObjectId('65b7216980efedfc5d06bbdb'),ObjectId('659d876db620d3307760c609'), ObjectId('65a00944c74155a97f0233ed'), ObjectId('659c09bb69fa81e86fdc59c6')],
        'Gestão em RH':[''],
        'Desenvolvimento de Sistemas':[ObjectId('6683e45f389df01c5baa1506'), ObjectId('659c0cafd90c3348d2ffbce1')],
        'Serviço Social':[''],
        'Perícia Criminal':['']}
    id_questao = random.choice(banco_questoes[materia])
    
    try:
        df_questions=get_df('questions',['_id','alternatives','description','feedback','title','classId'])
        df_questions = df_questions[df_questions._id.isin([id_questao])]
        df_classes=get_df('classes',['_id','blocks'])
        blocks = df_classes[df_classes._id.isin([ObjectId(df_questions['classId'].item())])]['blocks'].to_list()[0]
        df_blocks=get_df('blocks',['_id','questions','content'])  
        conteudo_aula = df_blocks[df_blocks._id.isin(blocks)]['content'].to_list()
        conteudo_aula_tratado=[]
        for i in conteudo_aula:
            if i!=None:
                conteudo_aula_tratado.append(from_html_to_text(i))
        conteudo_aula=(" ".join(conteudo_aula_tratado))
        for i in df_questions.columns:
            df_questions[i]=df_questions[i].astype(str)
        
        comando_questao = df_questions['title'].item()+df_questions['description'].item()
        img_tag = re.search(r'<img[^>]*>', comando_questao)
        img_tag = img_tag.group()
        img_tag = img_tag.split('src="')[1]
        img_tag = img_tag.split('"')[0]
        comando_titulo= from_html_to_text(df_questions['title'].item())
        comando_descricao=from_html_to_text(df_questions['description'].item())
        feedback=from_html_to_text(df_questions['feedback'].item())
        alternativas=from_html_to_text(df_questions['alternatives'].item())
        return comando_titulo, comando_descricao, feedback, alternativas, conteudo_aula, img_tag
    except:
        st.error(body=f'Erro ao extrair a matéria {materia} do alexandria',icon='🚨')
        return '','','','','',""
    

@st.cache_data 
def setupAula(materia):
    materia = ''.join(c for c in materia if not unicodedata.category(c).startswith('C'))
    try:
        df_disciplinas = get_df('disciplines', ['title','learningUnits'])
        LearningUnit = df_disciplinas[df_disciplinas.title.isin([materia])]['learningUnits'].to_list()[0][0]    
        df_learningunits=get_df('learningunits',['_id','classes'])
        aula = df_learningunits[df_learningunits._id.isin([LearningUnit])]['classes'].to_list()[0][0]
        df_classes=get_df('classes',['_id','blocks'])
        blocks = df_classes[df_classes._id.isin([aula])]['blocks'].to_list()[0]
        df_blocks=get_df('blocks',['_id','questions','content'])
        filtro_questoes = df_blocks[df_blocks._id.isin(blocks)]['questions'].apply(lambda x: len(x)!=0)
        questions = df_blocks[(df_blocks._id.isin(blocks))&(filtro_questoes)]['questions'].to_list()[0]
        
        conteudo_aula = df_blocks[df_blocks._id.isin(blocks)]['content'].to_list()
        conteudo_aula_tratado=[]
        for i in conteudo_aula:
            if i!=None:
                conteudo_aula_tratado.append(from_html_to_text(i))
        conteudo_aula=(" ".join(conteudo_aula_tratado))
        
        df_questions=get_df('questions',['_id','type','level','alternatives','description','feedback','title'])
        df_questions = df_questions[df_questions._id.isin(questions)]
        for i in df_questions.columns:
            df_questions[i]=df_questions[i].astype(str)
        df_questions = df_questions[df_questions.type.isin(['multiple-choice','complex-multiple-choice'])].sample()
        comando_titulo= from_html_to_text(df_questions['title'].item())
        comando_descricao=from_html_to_text(df_questions['description'].item())
        feedback=from_html_to_text(df_questions['feedback'].item())
        alternativas=from_html_to_text(df_questions['alternatives'].item())
        return comando_titulo, comando_descricao, feedback, alternativas, conteudo_aula
    except:
        st.error(body=f'Erro ao extrair a matéria {materia} do alexandria',icon='🚨')
        return '','','','',''
