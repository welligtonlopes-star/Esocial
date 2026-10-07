import streamlit as st
import requests
import tempfile
import os
import re
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.hazmat.primitives import serialization

st.set_page_config(page_title="Consulta eSocial", page_icon="🏢", layout="centered")

st.title("🏢 Consulta de Fechamento do eSocial")
st.markdown("Verifique o status da folha de pagamento (S-1299) de uma empresa.")

# Formulário de entrada
with st.form("form_esocial"):
    col1, col2 = st.columns(2)
    with col1:
        cnpj_input = st.text_input("CNPJ da Empresa", placeholder="00.000.000/0001-00")
    with col2:
        competencia_input = st.text_input("Competência", placeholder="01/2026 ou 2026-01")

    cert_file = st.file_uploader("Upload do Certificado A1 (.pfx / .p12)", type=["pfx", "p12"])
    senha_cert = st.text_input("Senha do Certificado", type="password")

    btn_consultar = st.form_submit_button("🔍 Consultar Status")

if btn_consultar:
    if not cnpj_input or not competencia_input or not cert_file or not senha_cert:
        st.warning("⚠️ Por favor, preencha todos os campos e faça o upload do certificado.")
    else:
        cnpj_limpo = re.sub(r'\D', '', cnpj_input)
        
        comp_raw = competencia_input.strip()
        if "/" in comp_raw:
            p = comp_raw.split("/")
            comp_limpa = f"{p[1]}-{p[0]}" if len(p[0]) == 2 else f"{p[0]}-{p[1]}"
        else:
            comp_limpa = comp_raw

        with st.spinner("Consultando eSocial..."):
            cert_tmp_path = None
            key_tmp_path = None
            try:
                pfx_bytes = cert_file.read()
                private_key, certificate, _ = pkcs12.load_key_and_certificates(
                    pfx_bytes, senha_cert.encode()
                )

                with tempfile.NamedTemporaryFile(delete=False) as cert_tmp, \
                     tempfile.NamedTemporaryFile(delete=False) as key_tmp:
                    
                    cert_tmp.write(certificate.public_bytes(serialization.Encoding.PEM))
                    key_tmp.write(private_key.private_bytes(
                        encoding=serialization.Encoding.PEM,
                        format=serialization.PrivateFormat.PKCS8,
                        encryption_algorithm=serialization.NoEncryption()
                    ))
                    
                    cert_tmp_path = cert_tmp.name
                    key_tmp_path = key_tmp.name

                url = "https://webservices.esocial.gov.br/servicos/empregador/consultaloteeventos/WsConsultaLoteEventos.svc"
                headers = {"Content-Type": "application/soap+xml; charset=utf-8"}
                
                soap_xml = f"""<?xml version="1.0" encoding="utf-8"?>
                <soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
                  <soap:Body>
                    <consultaRecibo xmlns="http://www.esocial.gov.br/schema/consulta/recibo/v1_0_0">
                      <idEmpregador>{cnpj_limpo}</idEmpregador>
                      <perApur>{comp_limpa}</perApur>
                    </consultaRecibo>
                  </soap:Body>
                </soap:Envelope>"""

                response = requests.post(
                    url, 
                    data=soap_xml, 
                    headers=headers, 
                    cert=(cert_tmp_path, key_tmp_path),
                    timeout=30
                )

                if "S-1299" in response.text:
                    st.success(f"✅ **FECHADO**: A folha da competência **{comp_limpa}** para o CNPJ **{cnpj_limpo}** possui o evento S-1299 gerado.")
                else:
                    st.warning(f"⚠️ **EM ABERTO**: Não foi localizado fechamento (S-1299) para a competência **{comp_limpa}** no CNPJ **{cnpj_limpo}**.")

            except ValueError:
                st.error("❌ A senha fornecida para o certificado está incorreta.")
            except Exception as e:
                st.error(f"❌ Erro na comunicação com o eSocial: {e}")
            finally:
                if cert_tmp_path and os.path.exists(cert_tmp_path): os.remove(cert_tmp_path)
                if key_tmp_path and os.path.exists(key_tmp_path): os.remove(key_tmp_path)