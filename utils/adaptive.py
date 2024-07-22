from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import AzureOpenAIEmbeddings
from langchain_community.vectorstores.chroma import Chroma
from langchain_core.messages import HumanMessage
import os
import re
from utils.util_tools import from_html_to_text


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
        chunk_size=200,
        chunk_overlap=50,
        length_function=len,
        is_separator_regex=False)
    docs = splitter.create_documents([conteudo_aula])
    db = Chroma.from_documents(docs, embeddings)
    retriever = db.as_retriever()
    best_docs=retriever.invoke(questao, search_kwargs={"k": 3})
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


def conversa(input_aluno, messages, llm, questao):   
    greeting_condition = guard_rail_de_resposta_humanizada(llm, input_aluno)
    if greeting_condition=='True':
        messages.append(["user",str(input_aluno)])
        response=llm.invoke(input_aluno)
        response = guardrail_camada_final_conversa_basica(llm, response.content)
        messages.append(["assistant", response])
        return response, messages
    else:
        input_aluno = f"""{input_aluno}. Atention! Do not solve the question. Instead of solving it,
        please briefly explain me the necessary reasoning to solve it. Then, tell me to try to apply the reasoning.
        Do never offer to calculate too, tell me to try instead."""
        messages.append(["user",str(input_aluno)])
        response=llm.invoke(messages)
        if response.content.startswith('Olá!'):
            response = response.content.replace('Olá! ','')
        print('Msg pre guardrail:',response.content)
        response = guardrail_camada_final(llm, questao, response.content)
        print('Msg pos guardrail:',response)
        messages.append(["assistant", response])
        return response, messages

def transforma_questaoHTML_em_texto_e_imagem(questao, llm):
    questao_texto = from_html_to_text(questao)
    img_filtro_url = r'https?://\S+\.(?:jpg|jpeg|png)'
    match = re.search(img_filtro_url, questao, re.DOTALL)
    url_questao = match.group(0) if match else None
    if url_questao!=None: 
        img_description_messages = HumanMessage(content=[
        {"type": "image_url", "image_url": {"url": url_questao}},
        {"type": "text", "text": f"System: Describe in detail the image in context\
            with the necessary information to solve the following question: {questao_texto}"}
        ])
        descricao_imagem_questao = llm.invoke([img_description_messages])
        descricao_imagem_questao = descricao_imagem_questao.content
    else:
        descricao_imagem_questao=questao_texto
    return descricao_imagem_questao


def quiz_orquestrator(llm, input_aluno, messages, user_name, user_curso, questao_inicial, questao, conteudo_aula):
    if messages==[]:
        questao_com_imagem_descrita = transforma_questaoHTML_em_texto_e_imagem(questao, llm)
        messages = chat_memory(questao_com_imagem_descrita, conteudo_aula)
        completion, messages = interacao_inicial(user_name, user_curso, llm, questao_inicial, messages)
        return completion, messages 
    else:
        completion , messages = conversa(input_aluno, messages, llm, questao)
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
    - The completion must be written in Brazillian portuguese;
    - The completion is not allowed to answer questions about billing or exams schedules;
    - The completion must stick to the following quiz question context: {questao},
    - The completion can not have Latex text within.
    Now, If the analyzed text infringed any of the above rules, here goes the actions
    you must take to correct it:
    
    - If the completion is written in any another language than brazillian portuguese, you must translate it to brazillian portuguese;
    - If the completion contains explanations about billing or exams schedules, you should rewrite to: 'Eu sou uma IA treinada apenas para ajudar com questões do quiz, infelizmente não posso ajudar com outro tipo de dúvida. Caso tenha alguma dúvida sobre o quiz, ficarei feliz em poder ajudar;
    - If the completion contains subjects too different from quiz context, you should rewrite to: 'Eu sou uma IA treinada apenas para ajudar com questões do quiz, infelizmente não posso ajudar com outro tipo de dúvida. Caso tenha alguma dúvida sobre o quiz, ficarei feliz em poder ajudar;
    - If the completion contains Latex formula whitin, please rewrite with UTF-8 characters.
    Here goes the text that AI should moderate: ```{completion}```
    Finally: If the text did not infringe any rule, AI should just replicate the original text.
    Important: Do not include triple backticks on the completion
    """
    final_guardrail = llm.invoke(prompt)
    return  final_guardrail.content


def guardrail_camada_final_conversa_basica(llm, completion):
    prompt=f"""The text between triple backticks must be written in Brazillian portuguese
    and should motivate the student to complete the quiz question.
    
    If it is written in any another language than brazillian portuguese or if it 
    does not contain any motivation, translate it to brazillian portuguese and add
    just one phrase motivating your student to complete the quiz;
    
    Here goes the text: ```{completion}```
    Important: Just return the rewritten text on your completion. Don't write anything else.
    Important: Do not include triple backticks on the completion
    """
    final_guardrail = llm.invoke(prompt)
    return  final_guardrail.content

def guard_rail_de_resposta_humanizada(llm, input_aluno):
    condition_prompt= f"""
    Context: You are a academic teacher named Edu who works at Cogna Educação.
    You must analyze a text between triple backticks, checking if the text
    contains a greeting, a thanks or a chitchat with the user. If it does, just return the boolean value True.
    Or if it does not contain greeting, a chitchat, a thanks message, just return False instead.
    Remember, you will be talking to people of all ages, so understand that they may use slang and dialects.
    Search for informal dictionaries to understand what the users are talking with you.
    Now, here goes some examples of greeting, thanks messages and simples chats in brazillian portuguese:
    ***Greetings***
    Olá, tudo bem?;
    Oi;
    Oie;
    Opa, tudo joia?;
    Estou bem, obrigada
    E aí, beleza?
    Salve, bão?;
    Salve, Edu;
    Fala meu mano;
    Fala parceiro;
    Hey;
    Ahoy;
    Heya;
    Fala aí mano;
    Iae, beleza?;  
    Tudo joia com você?;
    *** Thanks ***
    Obrigada pela ajuda!;
    Valeu pela ajuda, mano;
    Tamo junto, chat;
    Valeu Chat;
    Ok, obrigada!;
    Valeu, Edu!;
    É nóis Edu!;
    É nóis, Eduzão!;
    Valeu, cara;
    Here goes the text you must analyze: ```{input_aluno}```
    Attention! You must always respond in Brazillian Portuguese PT-BR
    """
    greeting_condition = llm.invoke(condition_prompt)
    return greeting_condition.content  
