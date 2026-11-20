import React, { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { verifyEmail } from "../../../services/authService";

export default function VerifyEmail() {
  const [params] = useSearchParams();
  const [state, setState] = useState({ loading: true, message: "Verifying your email...", error: false });
  useEffect(() => {
    const token = params.get("token");
    if (!token) { setState({ loading: false, message: "Verification token is missing.", error: true }); return; }
    verifyEmail(token).then(data => setState({ loading: false, message: data.message || "Email verified.", error: false }))
      .catch(e => setState({ loading: false, message: e.message, error: true }));
  }, [params]);
  return <main style={{minHeight:"100vh",display:"grid",placeItems:"center",background:"#07111f",color:"#e2e8f0",padding:24}}>
    <section style={{maxWidth:460,width:"100%",padding:32,border:"1px solid #263449",borderRadius:16,background:"#0d1728"}}>
      <h1 style={{fontSize:24}}>Email verification</h1><p style={{color:state.error?"#fca5a5":"#a5f3fc"}}>{state.message}</p>
      {!state.loading && <Link style={{color:"#67e8f9"}} to="/login">Continue to sign in</Link>}
    </section>
  </main>;
}
