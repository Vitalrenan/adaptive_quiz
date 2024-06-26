from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import AzureOpenAIEmbeddings
from langchain_community.vectorstores.chroma import Chroma

# from langchain.chains import SequentialChain
# from langchain.chains import LLMChain
# from langchain.prompts import ChatPromptTemplate
# from langchain.chains import ConversationChain
# from langchain.memory import ConversationSummaryBufferMemory
# from langchain_openai import AzureChatOpenAI
# from dotenv import load_dotenv
import os
from pymongo import MongoClient
from bs4 import BeautifulSoup
import pandas as pd
import streamlit as st
import re
import unicodedata

#função setup conteudo de aula e questão quiz
def get_df(db, collection_name,colunas):
    print(f"Coletando base {collection_name}\n")
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
        'Pedagogia':['PRÁTICAS PEDAGÓGICAS: IDENTIDADE DOCENTE​','PENSAMENTO CIENTÍFICO','FUNCIONAMENTO DA EDUCAÇÃO BRASILEIRA E POLÍTICAS PÚBLICAS​','FUNDAMENTOS DA EDUCAÇÃO​','PSICOLOGIA DA EDUCAÇÃO E DA APRENDIZAGEM'],
        'Administração':['MATEMÁTICA FINANCEIRA','LEGISLAÇÃO EMPRESARIAL APLICADA','ANÁLISE DE CUSTOS​','MÉTODOS QUANTITATIVOS​','OPTATIVA I (EDUCAÇÃO AMBIENTAL;GESTÃO DO CONHECIMENTO)​'],
        'Gestão em RH':['MATEMÁTICA FINANCEIRA','LEGISLAÇÃO EMPRESARIAL APLICADA','GESTÃO DE PESSOAS​','MÉTODOS QUANTITATIVOS​','OPTATIVA  II (AVALIAÇÃO DE PERFORMANCE; COMUNICAÇÃO E EDUCAÇÃO CORPORATIVA; LIBRAS - LÍNGUA BRASILEIRA DE SINAIS)​','PROJETO INTEGRADO INOVAÇÃO - GESTÃO​'],
        'Desenvolvimento de Sistemas':['ENGENHARIA DE SOFTWARE​','LINGUAGEM DE PROGRAMAÇÃO​','LÓGICA E MATEMÁTICA COMPUTACIONAL','ALGORITMOS E PROGRAMAÇÃO ESTRUTURADA​','ANÁLISE E MODELAGEM DE SISTEMAS​','PROJETO INTEGRADO INOVAÇÃO - ANÁLISE E DESENVOLVIMENTO DE SISTEMAS​'],
        'Serviço Social':['INTRODUÇÃO À FILOSOFIA​','ESTATÍSTICA E INDICADORES SOCIAIS​','ADMINISTRAÇÃO E PLANEJAMENTO DE SERVIÇO SOCIAL​','LEGISLAÇÃO SOCIAL E DIREITOS HUMANOS​','ECONOMIA POLÍTICA​'],
        'Perícia Criminal':['FUNDAMENTOS HISTÓRICOS E INTRODUÇÃO AO ESTUDO DO DIREITO','FUNDAMENTOS DE INVESTIGAÇÃO E CRIMINALÍSTICA​','TEORIA GERAL DO PROCESSO​','EXPANSÃO DA CRIMINALIDADE​','TEORIA GERAL DO DIREITO CONSTITUCIONAL','PROJETO INTEGRADO INOVAÇÃO - INVESTIGAÇÃO E PERÍCIA CRIMINAL​'],
    }
    return cursos

def from_html_to_text(tag):
    tag=tag.encode("utf-8")
    soup = BeautifulSoup(tag, features="html.parser")
    for script in soup(["script", "style"]):
        script.extract()   
    text = soup.get_text()
    lines = (line.strip() for line in text.splitlines())
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    text = '\n'.join(chunk for chunk in chunks if chunk)
    return text

def trata_alternativas(texto):
    itens = re.findall(r"\{(.*?)\}", texto)
    alternativas=[]
    correcoes=[]
    for item in itens:
        alternativa=item.split('",')[0].split('"text": ')[1][1:]
        alternativas.append(alternativa)
        
        correcao=item.split('"isRightAnswer": ')[1].split(',')[0]
        correcoes.append(correcao)        
    return alternativas, correcoes

@st.cache_data 
def setupAula(materia):
    materia = ''.join(c for c in materia if not unicodedata.category(c).startswith('C'))
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
        #st.stop()
    
    #requisições
    try:
        df_disciplinas = get_df(db, 'disciplines', ['title','learningUnits'])
        LearningUnit = df_disciplinas[df_disciplinas.title.isin([materia])]['learningUnits'].to_list()[0][0]    
        df_learningunits=get_df(db,'learningunits',['_id','classes'])
        aula = df_learningunits[df_learningunits._id.isin([LearningUnit])]['classes'].to_list()[0][0]
        df_classes=get_df(db,'classes',['_id','blocks'])
        blocks = df_classes[df_classes._id.isin([aula])]['blocks'].to_list()[0]
        df_blocks=get_df(db,'blocks',['_id','questions','content'])
        filtro_questoes = df_blocks[df_blocks._id.isin(blocks)]['questions'].apply(lambda x: len(x)!=0)
        questions = df_blocks[(df_blocks._id.isin(blocks))&(filtro_questoes)]['questions'].to_list()[0]
        
        conteudo_aula = df_blocks[df_blocks._id.isin(blocks)]['content'].to_list()
        conteudo_aula_tratado=[]
        for i in conteudo_aula:
            if i!=None:
                conteudo_aula_tratado.append(from_html_to_text(i))
        conteudo_aula=(" ".join(conteudo_aula_tratado))
        
        df_questions=get_df(db,'questions',['_id','type','level','alternatives','description','feedback','title'])
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



# ####################################
# ####### Funções de chat ############
# ####################################
def chat_memory(questao, conteudo_aula):
    #memory = ConversationSummaryBufferMemory(llm=llm, max_token_limit=2000)
    #questao=questao.encode("utf-8")
    #conteudo_aula=conteudo_aula.encode("utf-8")
    embeddings = AzureOpenAIEmbeddings(
        azure_endpoint='https://openai-dados-lab-poc.openai.azure.com/',
        api_key=os.environ["AZURE_OPENAI_API_KEY"]
    )  
    conteudo_relacionado = get_aula_rag(conteudo_aula, questao, embeddings)
    messages=\
        [["system",f"""Act as a very skilled university professor in assisting students on academic quizes.
        You often tell the necessary basic concepts to solve it and then ask if the student understood them or if wants to proceed to the resolution.
        The AI is assisting the student on this question: {questao}.
        The AI completion must use the following text as reference: {conteudo_relacionado}.
        Important: You must answer this onging conversation in brazillian portuguese, very briefly, concise and kindly."""]]
    return messages

#rag
def get_aula_rag(conteudo_aula, questao, embeddings):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=100,
        length_function=len,
        is_separator_regex=False)
    docs = splitter.create_documents([conteudo_aula])
    db = Chroma.from_documents(docs, embeddings)
    retriever = db.as_retriever()
    best_docs=retriever.invoke(questao, search_kwargs={"k": 1})
    conteudo_relacionado = "".join([best_docs[i].page_content for i in range(len(best_docs))])
    return conteudo_relacionado

# funções de interação
def interacao_inicial(user_name, user_curso, llm, questao_inicial, messages):
    if questao_inicial == True:
        template_inicial = \
        f"""Context: Act as a kind academic professor assisting your student {user_name}, from {user_curso} course.
        Action: Congratulate {user_name} for another step in {user_curso} carreer. Then just inform that you can help with
        the quiz question.
        Important: Answer briefly, concise and kindly in brazillian portuguese. Do not write more than one paragraph."""
    else:
        template_inicial = \
        f"""Context: Act as a kind academic professor assisting your student {user_name}.
        Action: Now inform you are moving to the next question. Then, tell your student you can help again.
        Important: Answer briefly, concise and kindly in brazillian portuguese. Do not write more than one paragraph."""
    completion_inicial = llm.invoke(template_inicial)
    completion_inicial = completion_inicial.content
    completion_inicial = completion_inicial.replace('Tutor: ','').replace('Professor: ','')
    messages.append(["assistant",str(completion_inicial)])
    return completion_inicial, messages

def conversa(input_aluno, messages, llm):   
    input_aluno = f"""{input_aluno}. Atention! Do not solve the question. Instead of solving it,
    please briefly explain me the necessary reasoning to solve it. Then, tell me to try to apply the reasoning.
    Do never offer to calculate too, tell me to try instead."""
    messages.append(["user",str(input_aluno)])
    response=llm.invoke(messages)
    response = response.content
    if response.startswith('Olá!'):
        response = response.replace('Olá! ','')
    messages.append(["assistant", response])
    return response, messages

def quiz_orquestrator(llm, input_aluno, messages, user_name, user_curso, questao_inicial, questao, conteudo_aula):
    if messages==[]:
        messages = chat_memory(questao, conteudo_aula)
        completion, messages = interacao_inicial(user_name, user_curso, llm, questao_inicial, messages)
        return completion, messages 
    else:
        completion , messages = conversa(input_aluno, messages, llm)
    return completion, messages

def gera_sugestoes(llm, questao, messages):
    conteudo_relacionado = messages[0][1]
    conteudo_relacionado = conteudo_relacionado.split('text as reference: ')[1].split('Important:')[0]
    ultima_conversa = messages[-1][1]
    prompt=f"""Context:Act as a university professor assisting your student to develop a reasoning about\
            the question below: {questao};
            In order to help, I will provide you with some related content. Here is a brief summary of the content:\
            {conteudo_relacionado};
            Now, you should provide to your student three possible questions that could be asked about the content above.
            System: Ai must always answer in brazillian portuguese, in a very concise and kind way. Sometimes you can be funny using ASCII emojis.
            System: Ai completion should be in the following format:\
            -> Here goes the AI first generated question.\
            -> Here goes the AI second generated question.\
            -> Here goes the AI third generated question.\
            
            Here goes an example for you to follow:
            -> O que é a Vontade para Schopenhauer?
            -> Como Schopenhauer vê o papel da arte em relação à Vontade?
            -> Quais são as principais diferenças entre a estética de Schopenhauer e a de Kant?
            
            System: AI must never suggest a question about if an alternative is right. The suggestions should guide\
            the student to understand the reasoning to solve the question instead. 
            Important: You must change your suggestion if it looks like this: {ultima_conversa}.
            """
    sugestoes = llm.invoke(prompt)
    sugestoes = sugestoes.content
    sugestoes_list = sugestoes.split("->")
    sugestoes_dict = {}
    for n,i in enumerate(sugestoes_list[1:]):
        sugestoes_dict[n+1] = i.replace('\n','')[1:]
    return sugestoes_dict

def guardrail_camada_final(llm, questao, completion):
    prompt=f"""You are a text moderator checking if a text between triple 
    backticks is infringing any of the following rules:
    - The text must be written in Brazillian portuguese;
    - The AI is not allowed to answer questions about billing or exams schedules;
    - The AI must stick to the following quiz question context: {questao},
    
    Now, If the analyzed text infringed any of the above rules, here goes the actions
    you must take to correct it:
    
    - If the text is written in any another language than brazillian portuguese, you must translate it to brazillian portuguese;
    - If the text contains explanations about billing or exams schedules, you should rewrite to: 'Eu sou uma IA treinada apenas para ajudar com questões do quiz, infelizmente não posso ajudar com outro tipo de dúvida. Caso tenha alguma dúvida sobre o quiz, ficarei feliz em poder ajudar;
    - If the text contains subjects too different from quiz context, you should rewrite to: 'Eu sou uma IA treinada apenas para ajudar com questões do quiz, infelizmente não posso ajudar com outro tipo de dúvida. Caso tenha alguma dúvida sobre o quiz, ficarei feliz em poder ajudar;
    
    Here goes the text that AI should moderate: ```{completion}```
    Finally: If the text did not infringe any rule, AI should just replicate the original text.
    """
    final_guardrail = llm.invoke(prompt)
    return  final_guardrail.content
