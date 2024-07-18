from datetime import datetime, timedelta
from azure.storage.blob import BlobServiceClient, BlobSasPermissions, generate_blob_sas
import os 

#azure blog setup
AZURE_ACCOUNT_NAME = os.getenv('AZURE_ACCOUNT_NAME')
AZURE_ACCOUNT_KEY = os.getenv('AZURE_ACCOUNT_KEY')
AZURE_CONTAINER_NAME = os.getenv('AZURE_CONTAINER_NAME')
def upload_and_generate_sas_token(file_path, blob_name):  
    _, extensao = os.path.splitext(file_path)  
    extensao = extensao.split('?')[0]  
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")  
    unique_blob_name = f"{blob_name}_{timestamp}{extensao}"  
    try:  
        blob_service_client = BlobServiceClient(account_url=f"https://{AZURE_ACCOUNT_NAME}.blob.core.windows.net",  
                                                credential=AZURE_ACCOUNT_KEY)  
        blob_container_client = blob_service_client.get_container_client(AZURE_CONTAINER_NAME)  
        with open(file_path, "rb") as file:  
            blob_client = blob_container_client.upload_blob(name=unique_blob_name, data=file, overwrite=True)
        token_expiry = datetime.now() + timedelta(hours=120)  
        sas_token = generate_blob_sas(  
            account_name=AZURE_ACCOUNT_NAME,  
            container_name=AZURE_CONTAINER_NAME,  
            blob_name=unique_blob_name,  
            account_key=AZURE_ACCOUNT_KEY,  
            permission=BlobSasPermissions(read=True),  
            expiry=token_expiry  )
        return f"https://{AZURE_ACCOUNT_NAME}.blob.core.windows.net/{AZURE_CONTAINER_NAME}/{unique_blob_name}?{sas_token}"  
    except Exception as e:  
        print(f"Erro ao fazer upload do arquivo PDF e gerar o token SAS: {str(e)}") 
