#!/usr/bin/env python3
"""Positive and semantic-mutation regression for the observability validator."""

from __future__ import annotations

import argparse
import base64
import copy
import csv
import hashlib
import importlib.util
import itertools
import json
import lzma
import math
import shutil
import struct
import subprocess
import sys
import tempfile
from decimal import Decimal
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Mapping, Sequence


INVALID = "MECHANICAL OBSERVABILITY BUNDLE INVALID"
PARENT_SHA = "2e175396ff30faea8a4d96d5a0336ab9ba042f12"
SOURCE_SHA = "1234567890abcdef1234567890abcdef12345678"

AUTHENTIC_A_PAIR_STATE_HASHES = {
    "positive": {
        "grid_gauge.csv": "f712fc5e194512736154efd26cfb7d14a6d7f0bc142d8577575a52517309a12f",
        "nullspace_metrics.csv": "8f4493dcf82c0fe6ba8b9b5ddcc20fef241f33647bfb50cdb5b3ccd78cdb1aa0",
        "nullspace_modes.csv": "61ba8628d3e56e78deedc6090abc9f8d488c7f03e347a7226acab727ec36a33e",
        "operator_entries.csv": "855359c8eb1eb9e832aa38a2d1b878a81893f65b32f460730133ca9523a235ee",
        "operator_status.csv": "8a422ce4b2cecbf6e7ab1e21437423cd858ff99468d47fed8228c44a223ab90c",
        "rank_status.csv": "b469ca92382834af117344848f6102e2de666e4ea2d2608615a21654a03d12fc",
    },
    "sampling": {
        "grid_gauge.csv": "958816021ffc8687343dd237be057fdea10646ace561d7b5a30b2bbe7aa10e63",
        "nullspace_metrics.csv": "c81a419a7cf5cf33caa9cc50b2a19739cf8d3016008ac55e29fc19e38e948899",
        "nullspace_modes.csv": "7d38b266d19042257c282b4d74ac5a4bf984522ec0e72db7b9d8112a11cab504",
        "operator_entries.csv": "902a0f2e0b14e8bc6e6b37d95d46d06c61186403d825197d8209e446137a1c07",
        "operator_status.csv": "98ba2f3b2cd8acad7f1087ff739374c18bcce19f58056582ad044ff71eab605d",
        "rank_status.csv": "464b4f3f8e59be07ef8816e5fb033a2dd2ff50b3543d50251c8d8d10577042fa",
    },
    "derivative": {
        "grid_gauge.csv": "958816021ffc8687343dd237be057fdea10646ace561d7b5a30b2bbe7aa10e63",
        "nullspace_metrics.csv": "c81a419a7cf5cf33caa9cc50b2a19739cf8d3016008ac55e29fc19e38e948899",
        "nullspace_modes.csv": "7d38b266d19042257c282b4d74ac5a4bf984522ec0e72db7b9d8112a11cab504",
        "operator_entries.csv": "d69cc3bf79cd828f0e11726caa3f4cec56372172b03541522cb4a623213548fb",
        "operator_status.csv": "60b7ed682cba85d75f7efd2d4cad920c756a1213a6c429986e2fd6e48d4ada5b",
        "rank_status.csv": "464b4f3f8e59be07ef8816e5fb033a2dd2ff50b3543d50251c8d8d10577042fa",
    },
}

# Compressed byte-authentic smoke fixture covering Candidate A S/D + gauge,
# built volume enrichment/nonrigid quotient, a real translated operator
# spectrum comparison, and low-radius/deletion topology-gate controls.  The
# validator still reconstructs every semantic value.
BRANCH_COVERAGE_FIXTURE_B85 = (
    '{Wp48S^xk9=GL@E0stWa8~^|S5YJf5|NlC)nOy)Tlf+6LoO1{j+wXnCF>t<WinJBo%R-9u;PF)Qe*d)@*~xH`&gMziu0(yyH(N?l'
    '7TjZW<XC~E-mOQ@9HBl!3}*ZD5gC!t_aXoKj+(9w16OmvI6!%1LAarT7V8&l(q<Mo$v{fU$!if)wH0Mb_#Vu))Z{wnKPO{O$=n^?'
    '5FjZn-}l-YWke)S7$Kbh1|uh0)+7vrUZDp>-Ns|s8WdN|_FaY$289M9r+vmsm~nWz6r4%?OE&BC=Wchyo2XfFf&N;}P>=%hXioJ0'
    'dbKFP=CbotiTLd~C$NR7u}8a;Bl+o|s47IR)od7)&Xzm+MW0<t2!oxx8;YVvW&<FKEq~HjMWUQo@A{<N1WS#St>6PpdY0b7X;bwN'
    'lFe-~c83ISd|#H_To?l8jO5Tb5q@&u-VjFYReux19yXZ;>tfg@dWu4zRa`yd-@Kb`CWP;qj{b{S^)4a;uY#X`l=+h(NjoGB*Ynm='
    'NwyTpy9Om=H6vs7q@2!fGnCsz(=>}9jnQz&#S)Ueio?uTb*$OJK6X?IFK*uPwsn!)t&$I%p`qEYZWi?gU$?;I%L8>Im6+evKOob{'
    '0UfoWH-^abw?>{K+!5D+?(qEH<qtFO?qAw!2H6bI^k7$nOKk1}iNLktYV&LIj_k=ilj0#I@wVG%yCeDY@*6E>FJ}r@?s?lZq6A{B'
    '9UlA`nohCN(EN(LHDmr13p0L_2u{m*q&N{}HjhFypkKf`>1_s3fiX^|Q7TiarSJ}m$Pde1fa0s$)c2`>8Mypds9Syns$qyiJ1-;-'
    ')EO~5*u-$x(Nqn0Bs+)467z0ERFo-_%_oMIus2##=R)NNQT%Xyws1`<gVRYB(d~i9uJl;A4a4oiu}W`|jE}SmPho}@KYAxuxs)49'
    '2LBeI`=JQjN!r{Jly*^tFV>+`VNJ(KR0iuwbTzw*;!2I!R6V{CQT^*0M%;g8m5_qL?GV^a$t9)vu49OFnY#z4&YIq@s$5<h{Ew<o'
    '!_7PqQ|wB9zp1z1EOa+|K;DK1+#Nt;0M$9Z+%`exOdM<1^e=uuQCkIpF-_Dd&@D;aSV+(qdjK2SLB!!MOYEu3p-M9!pxH4IG|k<@'
    'oyoqXC}Nvj<qF&yT&EH)@%I6t?vA%V<Tm(iHj9MOh4#A1snUeyA#F6VC?76OTvcnBeh<#4mQ*WU>#y`OiqU}BH8NfDB4f&^&TN_r'
    'KXEVQru;>^9C%@R`fga#kUAu|NRvYpC3-M}-MptN-;G@B!q2A|XPQH~Ds*Fn`G9){UP2C{kDaX>(^Hv4uS-xb1T%oscsiYbR*LW@'
    'P*(nk8(&M*Ps-*Um8AgFWASWsI2LdZ-4}jVhQUi~-#D&CI9&O`Xdwy=zv$V(+%WvxUzQ*dCM5)}$$#ImO8oz&q3NE-YreVl|MXxQ'
    '!@a$Gu~VJ&adufYMyHJL5#2}(V&$$)R+LccY;$zhyB;Shu)-F7xFfXRjb2WGP8LG+ckHN%PpOBixg~=IX(B`JnRe~A-=>Y>(F^2)'
    '#+uns7yNQ1wzM>ReBdo&@8$YdPeJiTydAjqS5@V2*p@eUFW3uK(y6#3Ifr_1t{HMzkA5k)F^pzAK9#PaR#=CA{{%b<pxMo%0m@}M'
    'XoC`^kNa*d5-IiwJxdx7qfFWzwD#V7%>EB9TQle=`%5>qt>DG&-#CZvwBc$*Ye4Dosi>G4LT*TEe*d_(Pifwyq9G%G3v2UH%^Tf)'
    '#1)xME%h&u9VlZsoHe_-da9dQqAPBT2JNxL^lOs-@;Y%WOu?VtKNRu#(f}v=MwEl+b+6Yx6SpwDi<s{fK#K4;NlAgJA*}6<D&bF='
    '^?Dehw;IPB4J~dC&)o3ZNpH-za0$zl8`g4SOlEABc`N$o0+^v-I!ZE^?3#DNJq)6OcVu^hK-G3#-Nqo^0E)Cf1#mM0jt5ID&_k~+'
    'hQ~#_#5*<Js|C~uA8utWu|ej=C~}Wk>yW_Y>FDFNrM}Bu#cTIe>9nKa9vSc1(<uhw^*$bsX<RhXy>RH7j~62Vjshg%YJOeu43<@6'
    '$l_fTT0fKPOQ^wlstn7*gAhS67Av3ycBlRbU^<5jPQNOMh*-2d#Ewf9I!1lNP`g{Ta`rrdGjZkvr<f!IR8LGL+E2<Urx#SuL!Ea!'
    'x-^o|^s_%yy$_17!y$5J=>r3J8UV3w?`uEa+v<2vfjQP<IqR3?oyAa_53q92{g^$BcG~%y3a{{+HeFoI^i`Mm<3KO&h3*2M-jbf5'
    'CtW=|Wc&?nQ!?_)c>ZZ(^|hpveq;bH{B@PEYefaDUdz76&taoeHY;BVsHWH!In?G1h6nMuV@IU0Mk!o6n=>l<E#Hi@V*Xqf7Nr@~'
    'C#f}x`i3zpb@h`|akr|}k2pudw}qEJFD?5!dE~PqEd$1tt;;gq^sGRGsfM+BeM+@1ZNhAAMtQ50k1Dg$nc<2G8c=2w792b$s$#8M'
    'WWD#f$cQP{+qiNPfX^CTOV(pd*ix5))&@|0YJ@2fu$$1Ts2PU2gh=m{eEE6~+XC38{lzbVfI#A(Id*-TtCuy<1xGZsqV{g6dJq#A'
    'f%5kXtbp~Mr-arWcU=#}M!b9u3lThzP;OoayKU$<j>agzeBdrvWYVkXK!?&ls+jEZDF*vG)VCdq@w5~<SQZ2090Qx#0&>5ZvUm{7'
    ';l<43e3tb<x0O}YM@$4K{cyyToDOM<&3V`a>o>u3<*VXg_gYq<KV0WMAtlO}ixLvdPtCWaORWUwuc?3%{j<epVRz=If|rNZGY<UU'
    'PNSUemJc;Zz8nIMW6=Ss7G0R`&Ap%wL@8;)0oS_kcefv_hm*v7<N4VZEQ{>Z9~|F+iSA#nw#2gWUag6_ayKh5qIPxXE76$L%a5rM'
    'U)<v<DI?VLay03A&2WjhqRl9p#3;~l7kv)7yKw-Ko7K0;;EmF<i6=TiMY3;Lr1iN`@KsizF;ze^Bc8&9!O-PxSQDR6Ibs<6_#K*o'
    'Lx)nvN%DnaYj-tXp}{fBv{NOGDa}F&=_rUdbR3;$cwjTtBX%VbFUJ!#qMty%6TJ6L42(?*TpTnMgNzgEg<a5)nL-=WRRRUi%Wg{3'
    'tuF%lFl>svSVdMRl$NA?;1gxo)*ZzTHiyr_0wquryk*0^m?nfWpL92z%nX}ImZyG;t1?(hA%Emd!Iyn%bY#nIcC_5eyjX&^za@EI'
    '#)m&4ZdYmikalLGz2bLe-!4?c&*(TX7&_J^5c<El(JSuxjvz{VKX>Udn)=;D-Ze})@J_5)q1;^2!z+yOm$WAMM1Zxf4(16yAWYaG'
    'xvez`E3XkEOT-z|nm=qyYzr+jzYr~SU8-{R(vJ&=BXXmECwj!U7{QofqoKCBH=x@E%m1q?$u9%mP8VGwt=8oDa*3DqN&tRD#Ai!%'
    '<<R#nq}6VMv878nw3K@&=_~tXeR%IjJNYEH##I@*4QI#2(iW_X8|_;7eLZ|xD8&!d^GKOPLQQFVkzfs)w9w}_uPu2Q_Y}&$isEx9'
    '0>f`QxK<2@?CTZ*c7<M^U0XsO%~G^D@vmqI{(8J!Nr>A^wJKI;KTK~t!zR^WAZnP3%Bq<AysJ?JR^+}-?_u$a(Wms3+zkS<k+_jq'
    '@iJ9oj0XQD?NlVb_j#rSk`|GOqMLEv-!qJK6pK`p&iG9Tm3cvwL9`3iNGZxPB8=@@TA-*rClv|jAf_sXi(9^3u(Rvt4ECW#k4q@@'
    'y*{5A=+GkczFD)l%umPR4z$DX^iQhnL$ZleV%q}jPGPv#s+UWkzhpY1gfG8k<bF$=fYSnuTLm3lcJF(;_JGoZ;^zYHqK2VFV!RX%'
    '(NyE$&5>OWd>C%ADN)Zp*@K-nA#62BZR!VR-FkkDq94w|)*h+<qd!4>BF=ojUn;dxw-#9!#2^8bvu~w+0DJ|+*Ak6EljD<|%^?TE'
    'xA8;mKymF2t$hdO1kq-d<zjD}=|02N_MJAdOF`;&uxrC@4{O2Ifu+>u@G)HUjSEj+;nR%;OJpry!&2&NcfLWR_7<y%HMyi<vPR#G'
    'xUL$TZDV1N_DbY_%X&J}I=EbJGvc7XDWy4Rj8jFA99)vZdiM=B=Y9~Rt4vj=iGG+j2j672n)gLen}XKL6czn_LW+ulQ=Q;wKT^mb'
    '{M!Yw9dIFgRzg=nkr|1bh6~uj?dl_1NsmO7xPq_qrA`DyHljlA1O>5V-c(M5i8SMKDpEk=e}(O+r+e8y1+PECF*5=;sFd~moc2a?'
    '*}E3QrkNt(4E}-fZ1QtW25I6Zq{K`mmB9AXc!FO&kG2VM!Y5?Z6eHHbwVWY+$Fh2Facxy`2E*1*GVMB?1Yk%)c*C)m?Kn=%X-Yay'
    'Z^4LxCFpIQ9jn=Lr#CP$#gnOQcbD+QCnO4vwh%`y%fV2huG0}?K2#6joQ$OjH)|~H?)alm1%}jmxd@2jm#g%-XmpFp=ZBI%v>x^B'
    'hEY9acaX~li7p0PizE9R$?Ln)V&6-)h|wDifBLvZ%#5Z^U{$)GvBCCz0;-s7bwFg^*sWd<3DG_dS($pXo?*uC+*_+*eUM?w7=fQt'
    'R-){?E{^wzUN;|mtkVH>WfODbz-z`|x@`c^oZMl($0GZB51%S)KWlOmL|HFP03f5`9jr7g-*!~N2aikY?4OH_(q+~?`QQf&`3D!w'
    'unat+D3vuKuIy27A$*%r8(Gduf%?5>VNT=jha8AlMMl+v%TYTSB46d6#7dF4DY&tiSwrlq1TZmCfBY9Vu^9$v@lBL6Raz?(zbFK='
    '{s$R%GO?MJ4hF*u$$UZ#*cRt77o)Cz0lN8DMM6<)S%yt~nQ6x2N>WkhiLjz4%_l1i;2A~kF9=BaCxMFFGPL`~?ekh^OHFKMRj&R~'
    'fJi(@;!;>0H8g=#<!FVpKJW{z{==-Z(4u6-!wU^fl#wG)BupyElFBvUji~qDEtK9uefazwjV^B+D;H}J*vy;)TVKu&?=2zy#*v$J'
    'c4A3+KtJb52@ID8r2Or$7Heo>qfP}+Tx81neYR`j&djKosHXk?clQNF)ff796OfgTP4&$};yhaYO0aR$9f5rFV4PgSea(@%0kDK#'
    't1R`@M`YXi(v?C9(<8S#qcF*n13hlO5fY7h=MPaEte90&*bv>+e3L&g#oZOHyZ4?sksBX%389O9y6dh05GtcCpw{wo@kMBxrNYQ{'
    ';}b~102ptYf*}w=5`BSn-ng<aRdnew8;N1c5zvlb{n*U=`5ZnJp-;LX*6iQf?{|)uuI`#%m&fXArOa*vpOz>(K;pmI3BN1$<A2i*'
    'm-q<8k-07ogKjo-y+jJXj#@LGH=ssiaS0w`U3F!aU~s`CxwNRNV-TjOHSUvgilJRbbTX0ha~~or-25trfbQ#uKgT;oS7V5?+#qB;'
    'A07&?X}B7(1X%YvcX+!~GO=4|ljUcLl8k?~T<VJT#D9hdox5N78R(gKu1iCSgcuG&iE&1b<y8TT_;X%l0$@f)gY)DL#%#)Rt2xZS'
    'c^<?uR%4KIv7EHovZrhIN$?tXs=UaMs>7tI#OoU2j2pVcCF@f)ifzxT>9OG($FY=$_^+72($V*Mrv_jliM<6*v}k};R>1FjlU;M}'
    '^FsWbxkKvVgcCXeR*|zz{QF|8O`F#*4326WZ-k&6=7Vr^5Fx=$*6^-FmK|X>>0YQ>&fOfK?jNJpI_FanpnDY}3^WyLAXoMKi(Sy%'
    'YTGYhl+S*S-D_O9U|%9-I|9+S29E0KtO=IqCM19K>bexWB}j3}S`|gkGGF0zQH$~xC`#S_iFJinebl_f|AkquwH}?}Z$iK`JdU2L'
    'tQuSTJNKl|AV4p{E&7X*f^Mv&;Rf_(12)7wEJa`UCpeT?MccDmIv2KsO!-NRy(k~)NY8X>DZ#1<q&EFVL{zob8d}NmvlP9s5@i!<'
    'm*cf`A=p#Rjfd2jl4#_o!U@8TlMax^`b2-Xjv*iOTBK;B@$+;GlDZ^4K`Pw_Z#C(+b59%2C{)ew+S^u;72kRksJDTt(z0p2tBk2b'
    '(I+RLQ{TOCZln9>o@Zu`5N6x0n%KkL?bm0w-#j%>3Ies7N#edHuIA#1kcisQ8=YYqdB&!KllBY$X#~hU=MKSK!J0@${wi)e*FcvE'
    'h;_hD>t+hb{0#xk>9*MhU`gS6^NKIhdePz7`0BCPJT?%RI~iZ82*4~mrL&8EpNEB8sD-~06)FMYm$M-)^%>F-x}-V&WtygaIE@T('
    '-CX3vD+X%L@LV|-dKwLvq%+ywi09G1naTE?v8APo1_!dXG53GQc@<Ec*k;3)=z|Qu9ws@M>jU5ZF!5Xkt^s-}^iyWFZOB5u^>~SX'
    'DxJd7L0aPn))1rlFgKqKw>QewHeAM#{>rA}%F}nw3~(rlbr7l>_1oC>hV0r|M#uR{q}3-<-7gVOX$e1sCDLT3Y4`4{V`<?7`efK}'
    ')h^|ZsMc=daj6nd-tkF_m?@bb>lwvik}2}Mm!Fmm`CJcjUdC$l8pp5Zwh!@-eE_uMUk0nO(Kpl<)P#7-ZbG(RElELa3qEVGGu5D~'
    'YOl%yqlvF_aeA|jc`qf2;w(Ux8|yU@D%SY$*(W*=kYIqFpZ@w7i-6-?hoq2j;~*AspdUi0`;^imyA?483EN|~cRyB}Tr!6@VF>C)'
    '2+>{NNU5AWrqz&W8Ct&ntTfXEUqkI$OCU9ULCJ2~(ueEw3zCY6>C}a`5r#KR5L{fp2b^T*qOVXA6+j*g@Q?NZus|0MK}ge<hY~~L'
    '-4^0UG)MN@uw$6b5|kJAhWwflp9AGIQ~ow#Ok<ieB;jFaaMY~8zYjM-=?KIzRDLzENGup3ubEsOs74kTbe;PkNjYo~Z=0v<P{iGd'
    'RT2rQc=1!@dVr7iu|p6XuC`Wi(4?$%Kuhbpqgo2ZZnIqbh{Oh1SPe%xHX>CF>zs23UBk_WI!#)WQloFV$nzSnhVuAo6LF|9%G!@D'
    'gT&@1z*YnKxx~hYW!jBFo=v6JoUE4wxJ;4XS|E>XLq&Q~bhY;|m#Jb@T+gU*%$sDoy24cVFj5{X;9%Nh#2YP!EIiMGdqpw}ikHI-'
    'Q@#0R6pCmGm54M%zL3BDN}z8F%?%@tPVx6?lH_1csXN3SD~`TGd_kz=Qu@=bhl+SaAL!%^E0`{#N=LY!tG1Nbv*L~j75RCo|0XWJ'
    '$3dTixsO}G7p*ow<>mdDrNQoriuCGNJ?8<K4NAh2T}LFM0k%X4mg*^BZ|~89&vxWo7VwAoGZN11F33wNL|K3mv)VbXnxxLEr7#^_'
    'v3$wY#k7$3YY2>LSv=zxioO;WZYp;lm*-5EOF#K!W>B<5UUT~YF>6?s?H%zS^r+}WFL$rveU`|eth2lTgC5{d7hFiy*tb~d{qvE&'
    'W&R98Kg(J7t>iH)ES$VZ;7Y)Q&31O_i&2jcdVK;8W&qKw`@6UA)nlOC>#L#v*#<hHO;2^(Q<2;3HE96S)1-E62?l!bt_Gxf-{0V8'
    'p!<dOd#9(L1kWiQIsj`9#Jim^$Y~=g<Lka}ppcYl{G0nQU2G8n?&KtrUXA!hT*rp*Cg9Zr$u%rO&4RCSgokJ!1FG{otrZ9h991|+'
    'vPL3{&AvtH&fei_%iPL{u160eSFzynt2$-T08h^e1~hk*s9yan@xc5JWlcs^^W$y$V>SB?ZW!14A)&?=92sY{xCSx)Y1RlP)ZytF'
    'Abhh6d>;zzCb`zrq<E=m5v3f$5%vKq7p_@?)%dg2Gg9yA@if4d(hvP;LZd0hAodz|AAH2^M#N){52MyYYdJRB?Q|?$9vIH%xMWOT'
    'j;a)z*oQCgT+r=~y!qGhIABW`e-Wj}_j@T<xmJnH6Zt|lr&ys0k#f#sNH&Hf2OK&ig46AkDNRLBH9yfg+MnIFpNtkP5)$n?&?`9w'
    'B0sL*EAJt)ys`uDH{PEnhUgA2jtTtYq-Y%^d3GQF0CYgQV#!$Pz2%7R&zxSQrnFX#Ft5<2I(D7_i$&h~QwDlgG!@nF4eZ6{kR==P'
    'Qt$v-qb-2$S#)z7W#v+L$D0SJOKVihny1YCbrh8XhD%Yidt2VYHln%_+GxGv$~^TvRX74>^r3g9mAih2GRahCP*19y=&nHeCB>U5'
    'zCk0_#sX>f9-*(z+_ZWN^=c)84o|HC{cujZ-pWnQ#O9TUnsEzmHNhwu)B$>AAyys^T8i^9#A2D}%vT*ZXA6186@Nv*v05#6nlv(8'
    'Mn0GX>hev~86Ff7?i>*sZAW-{?mi2m$I4d-EyA>*i{0TKRiX+Z_`(IQ);axG0^z``u0Cd0ytHr%;o&62g*tYbzCAEu$&XW7OzS0v'
    'TX-!74Uu^WX$UMVEf*uRsJ58>L9pb*-9M#gbH^`3#b~lo3bf(n$fGqV!~7{<GMaVQy4KLL>8qXwRgn%80@~%L5HT$D-J#@EkU5L('
    'S$(+{Xqae&0FRU4T4g{I?~}c^GG{K!JP?P=eiVK?qi0z+3@$?`*dH6(;4#G$=IRs0rY2h4X-_cM2=WHXQs7ZUA<49>S3%Yv6TN$R'
    'R-q)^J5BYo=dm$q5n>Evj-F|0fp;!rz0j(eIJ$u#>uNC&N@y~>o_YaN<dA-eyExB_b58#A+H!<!K+Mtd_0eZK6QE3>A%M2tLxf+A'
    'P@ig?zi)@~S%u}~W$@@G9%>;XJ|099EKX!hh?_?l;yJ?LAlfTTM@D<qx4)vL<~tQpT&Nigl=u~w2{OyQ0c5FEG<@#^hs&<M8NlB*'
    '30BsE#Ho4&4>#eOkMigLpy%wy`kaM8HhL_hLwGY0#5Et$jX>HMr+6}tn-PwFa(irU!GKn|L-!mRlBRgg?H?d0idl=!>2;%Re8C`o'
    'kB0x!T(V|9HsMd`lE!^r+KMuZg*pyR8mdz5@1?ZCD;aOk;67$Dbnp61@&IT?^+D(hCknino?BKICsU1!f#})6U4*=%DX~4N;taA-'
    '`(_Z))6S?t79~-1;%TzhdGhqs9K=?u;LH+tg5fXCP!p#Q9r4*Gx<;c0nLPmmq*f4flU|-Nq_#4RE#r!nL!O*j1F^v#_9o&41#IBC'
    'l1ie%`7>?qYn6NeO-No2ff@Nzy8wO3o-R?wFL}76*1(lkqkPbN-L8j@MjWch26VHxK+D%f;up}84`~X`E;U}mW;HUq2|xX0;>vtn'
    'PV45b)guj`c=W)h-}9(ws{NYMP8sndU?Sq$J2YdVVHB{r(IvXtIU*qN6<2oF+yP^-qa|MUOyvdd7|v;j#Zi>VciFl5XXbbCfaaf?'
    '^^7Q8-3kN_)h2(n7&^Qw4m9hiN$Yd*+B<;-KHR-N{OoA0GRDJ8tr>2YeXA_!`j+pNDjO5^66rC?p8<^No*~#O6&V_p{3{YrlN*g}'
    'F(jA5EYkO8dlJ*;glpWI*k=aW!#AW<h+6nsNTeLhGxIT!6CRXOVuQsdzi6V#T+fCBkcIeQW;$1yXvXv6Byl6x8X-#hb`7+`;ghIG'
    'dA@pcD^S;Uy};lj253%lXN_Q!%+Kv6E7+B7D^g}Mh8+$4zrr`3(*@7J4jVI49Wjah=Yi4$$y*IE=c+^W?xh;{n-TN1br$eu;c763'
    '50^q#mIb;jAzu-aa`r61To%4>=hc|@W+CzQ&1coRL*lke<v%5LzUPuMb#f#hTaF9pEaGA2s>`)6yN?n6xcozi5ijXa9<1MNA$VFH'
    '%!V5`sknK^rKak7I^D}II=z7#ZRK5SOktW$UbJn1i#X!oYH6-f9&5KY&!Q7>nj9^gu6rA;fO5$Kh^^e9Gy|mWl_e0e;BLaRf-c5j'
    'fHX8(x2RuCRu6@bTT0?B@aW6^ROJW)#5@}cQ1><^!1jR+z6ENYi31lL^j3oVLY5^%#`Xw$#*qb4)iNGH|3vfyj4k{YQ~f06{ZzY*'
    'GgZkZKWx))PAE(MJ=6BdTJeA75z8O&RV9!YoJlxMjrwC4@Gl}jzwG6}t@ft5U%UAZqzgPAZWMNM&dC|k|9(UK04KUx1lI)vE<c18'
    'XuHr+$N1<y{`MvQ{+gV>Re!||*TG%f%M+EAQ$QDrel>#qeC%H|GFTSf^qWzl8{9L?C8jhT;wb}|D;rg(Zl6z9D+ftM^~-LA`j9{d'
    'D2_V+d1}w5Bo3JZ!5&IRbETMte_S7x;g-N3aW7LoyPlCl8dwv|7{Ce894*2LLr{-sZzAOE_ls+?3k62;i|kGDuHEP;o!z3|LgV9E'
    'rNIpY`+NaCAs-`lj>7^a`X@CC6)l<q7x2$%tHL6o+fGPxr@E^=w8)O>*VFTACKOrLvi|xO*QpQ4L=nh~blj?~R4Wa4AMO2$FkhF#'
    '>hx@F3tNi@6=jSgtZQftbzzUl#9<6Fji?+&RRFZ?;$!AyhzIQerm{y%_4WOMi_JK5bLT|-x(VL}n`8|2eQKNA4UI0F5$2f{*)NsM'
    'X}`^wWWBMOIsIf!o&xA5A2@DW5_Ut-0VzeB+*i>h9TE+Bx2}_r`9CrJZfLq;$v7l-z>nojs;E@>tfFaE;)L=azLoM8M9P5l6RASu'
    '7im$tJ3iPbuH-8xOlYCU&G9r|U8*hu;FZAqFm$S%`C_D2e^TX0i2<!K_X&JgPzboT?BFv)|F0CL`c=$PFisD)slXh<hv7al&>fT1'
    'Zg|s9vYve_Hu7b~?f743R&((v@Q@7*LS%V~_orsqnFz2<j_fGf*<wE9^=eNLolREK{Ig?QdYED5T{_RtWUQ$J*#^>QY8QYrM*aHx'
    'LGAm&g89JM)%x#__xnFS+*L!=YHG(B<ob_vS%)V{h0JBo9P-X!vJ*-%>pKn<XiivM^k7d|fnyTfnaDak+Of5D`JKV9G-uK*yXp01'
    'q`KOTQJdLo4_1d*IPwG2sw=2h)Opp7DK~4MNImfbP!i9Da~=tkjc>-qYkmd0Q9B$S2zPAVShHSLK0Wj!T%}Z_iBk{m=ph1eR3ON%'
    '$FUUkK`72lQICZ5t8!zkpkr{bxz7bf7C_Zf<p~Ij#9zAK)w!P))OBT`2>NEDl4NDg{u?(HYG3N;fcE+vub5Df`WDraXu6(avw})S'
    '9S+TB6&V1e(ORmNEMuQ$cxh=`!J+;wdmNVU4L5USH0gVrc>29VA;L9?T?(++C_UoI(3Ix8Fl`9Gh!C&`(U`{Cu;?fsEZX9^ORQe*'
    '%>{0IH@Ss7AJ&~B{wNKui^#p<CVj~-L1L*>7*})@M-;ie5Ze7(j{`c}c+ejxFyi20^FYSeJKy+0G`+3WZX3PaN`56x1Xre|f0B4*'
    'FugN`reQx9{Y_@B5s=i^FnM-G4HiVLoSCyzci(@tk3qD*P%<pT>06?$^SjPmdJPreE=8a1tt$>(!L-r?2n8b&uz|F+G*!yPt#4>r'
    '{Ad8Q$u)o+l_5mw(DOV*;EP$X<aX+<%$k+gnl|wp7nOTOzYhUdI%e;HLoFy`{Ct>sn}n~y#S<n!r*P>nPiEBUqFaF#&X6zvu5%I3'
    '5SX}cgGh<D0kCXs{<Pppcq;PVq5sI+=(B}pw*AV7mAe{$aQpA9t}~pLu&Puib^la3p68hAQs#9nu3wug7T;{eM!jT}9AO4~q}+35'
    '3+>w73*#Bh@6&-QIz|d(rh3pOgFPyex4yK|b|@rwO8=4(8%dJH@2@f}lAFQ-8TQ=U4dhwe%6Gc)-G(;T9>XX(my5%FQb6Fx*I#E%'
    's@M?F7`S7?GM8Zp*x2d~KZX&%3qWXTUK>In^vI2nCg}Llp+7vUqvl(Ls0J|yN7`?)+Vf?H^Tn#L@PUI|_2M{y#8yO(+$9SycHz2O'
    'mKIT57;-LoOIP2F#=SX>!8V%Ssl~t)^Oj~EtQcpbbf=U)4G6<;yhQm6*B*5$r0>n!W%#=(<5O!w$YX_)MT{5a%y{x~F5)jx{dQuH'
    '{4Uwj%WIJ}X>><dPX<bcz+Jnwow`Z&6x4?IU&hvR2ewLTz~4`aLV>N^VHUzA+4qRSO&lqaY<+e~QQrydt5Y<7k09py_gV?>x=@J8'
    'Tx!kqu!0(0FYzM3NjwcqmeoqR0jmEe{2&>h*P04Es4{i@>Q{Cg2sPL6dcYE$NC-U5qzoR&JOaJ_qEEZ4B0Lyj&BK5;np-OrSUiU='
    'mrm1keb9H+>$Yqm?Q0c*2VbxVfp{7pKrIBPIW(g!5FP8tl~qdE+Dw)%tG-_;2qkF@rdar4^djW-L~@G<n3w12gZQ}0p%WG_hI-tp'
    'q#~r?RD7}g)rCHYl-O{!9}03oPLee*)k-KK5?985_u96NZ@T!3(n5D<-4l+GPxQk2%C`)g!=eF(FL|>P8+giXg}raw0dnb6i*ugx'
    '@-dB7if^#}As>RC8U3o-_T!*mHY;(F)OB-zxCvn206fb_*q3%z%cmXWwDb$V(Eh`|L!dQoyETxd)&M<gj0CpodUNT3w4CwuJsKjW'
    'Lc|OiIv3@U-*Xgvq$<9GWMijIO@hb@FwnOMt3z|r(`u{Fr?6xI(vyuam-_#Gwj0Eh3-iI4%gXrcW0sHbv&M{nBMyM8kJwTeSsdQy'
    '+T(zRfFnvArdrLa4fw#+Ay?L`yd&8subC(H!VEsteklb*nr_)Z==}a|?)AyeRU8#iut<R~^^xKo%K2wtjtL=v2!bZd$APV~MxwXF'
    'jl9{g%grG6=RlaJ-MTOfs*BM1ZwWzhD9Umn@pyVDsuNR^m)0m!hzHKB=t2C;JZn{F*E~Qx&Dt#{?6H?G5LfD>w99NDp*M5c2j=xk'
    'l3e_Lrisyjt?bFY=1X$N-IHF~Su5rOSge@yZN&uFc!zM%FN^6C=UJPzqTGhqYOU3b1paNIb|qWQ7R32wgEvyj_B>as@vQv#&lvPG'
    'KKj!e4yu`t_gg1HpP%({2+Jy83;Vo`NOKF)ADm9_wZ%Wq)Nk1)R=dW$gbgD0IiBI>q4QO6U1EpQ#1iGRaN>cjhoqP~lL--NQgxFh'
    'lKp_i1Nj{AvSbr#=L#N?RCZVF1$jC)4+?lwV*H2>rimmWLHUj6A8KEg4D~zJanX{AuI^8LKjB$cbWDFv9rWVktb<7&zSw7)Yl(Wt'
    'mG}F{P#?QxbwD6;gi|EWdKiAwp#JZ`&`IIhVPJfxkOrn5NG-WXo$JRW-*K_p#%M3QiF?y7l|og)yXKQqqB^k@yGs}ol0!3GHfxZ5'
    'x9)B|JP)^m9g&m5=zBd6n!k33RS(nM)N~{I-<omcJfWQv>GRYlK#7Qs&R!`}a!N@-%3ZjbB28e^bOb}P&~!KT3FImQmrk;}9Z@!m'
    '2qaSN!8`wjjqGnwGT2<SKC0N1DZAVNaVnP$6}HTpG}1LHht#}M`-_fG=qEC>^VejM(P~4sT9-n<u5q9PqRT4N#>wb2I@LkU=ZxM%'
    'S<R^O4T-D*<1b?|LR>3ubX5%{!>O;)_7!lN_%c)#ReSR>`jQ~jJ>{<6yRMVfnGlS?NQRJ0wkhe|fS!I5j3Zp9gshCxKebM}k4n~*'
    'tX#8~@z4*ZKi7&gj>|;olQU+y5sMS_{t1+&4b(7!`3^TPA2BZ?GPSf5)ZJob2n%j4<tQ?+HyQ5^wqFt@SZPk%ysKW2P9YI>_wnyq'
    '5K-zl-8VG1^fAwz$9Pb3?b}-tNS9qG^hJ?rIJQ-VPG<J%lFIE`kZH)BkkUQBlXz#$M_}u2l||1nqIDAN44}z+u+7=<SH9s+YkbgB'
    'SF^c}&ZAsW^`N5Eth3X6hH{?{@Z)ld8MGKig+zsS1{>JZcubMt#nN~lUocN)g!&~Sjn81}{R!7lL$sc>jq|kI4STVg$^d?+VX0*y'
    ')bO%%cWn2IFK3nq-%b;p!I_6pXR}S|83=wCmMqdUJJJ8aT4c0mcu)z$2{;%+TWU@<Isqv?Ic15-@2tf+5G0%q)fL`~&$4h2U}Um6'
    '(iMReA{h*{K5oeYzxwO$)-2Jyg~|iJ5SzaHAqV!-MCal>2*NRmq;@&(>vg$_yD}mH+;kDFNBE%28yin-g>;|~651c(AqZYdGgYR*'
    '#Aqnc+!$;_usO^@tqlT_;M`=ZxqnUtAFRD?0lv%vL+CS%+nB&71E-wHOZ#?2!#7MH7rW9oqD|u%=#7X@eb8qf6TLzd5ZCt)gdpb5'
    'bv?%@(+#5H)MKr{6#J5rx2q9EM&ZNzk~~)|u0bu60Xx?5I8IO_>uE#=y&FBVg#78x2ACl6pU(KVJei%08pMy4)$dF^^Co#6Xg+vu'
    'SR-x6SHt@HCx7mCUWA%M+(+FFds&CI0wIls^i%i{={&8<c<L3O(7wS(s|XLT@+R`<n)aq9G)FT@Ae|<xVtz}tH-e~AvhgwdzZN^f'
    'kX-5}!rnZ1q8Hg_dfB@o{skIIRGh^#4BRwyZ)$!-55AG8550B^$va)$xaKS|{c^ut3mlc1kBN<KCF(&B%lKC(MJ+}tU)_qy^4Sb`'
    'G)surd<DTHa&Xk$db{DYJbaBtG5C6d8+5oKK<&TI!~+tUk|mgKAJFRQTCi48dK2Rd)6hze|H9@pcUU<NTDVF$en(e8Fva-#>pL#8'
    '=hmf-EeChPB7v=u0W&j#ywF$Mnuy~QWSYEIm%mgHFm@ILZMe@tY4|w-2_o(m)CWuFajZffYu}WY0v>zw+ULfBD9JHHMIG_In@vgF'
    'TdD&h^N;jN7U8-f>)Fya$eA?Mr@NjCn&+_#9cW*cc1b|U>#jIwkDXW&8#1M@`2-&O;OA6oZo?c!EN3&4<sS=x2Og4}c%#7!ZbJ!?'
    '!Xus=A4rGq7T!fKcD_eczhO@(?n8+0x>q0Mn*jIk*69~^800WQ7>2^gDs`78OfNK=3|DMN&_u$E9P-!?nc7O8s6M!<8=W&HUnQT6'
    'oIvq_5Y*BbXpT^*V(nw1Ic^w2){z^qxN|^7on0}5wxintgFe^YJ6##+F8(0Krsc4;avG8UYRL}Iq%X<iHH#~%qQ(E70=OBr6=pT#'
    'fSwI84>IEXfpXade9TmoKH(;g(S{XcPTxv$N^Xpe*S3kl-c7iGIebVZr9mX(l5e(;;KfflTuQ|mtmqRfqB7-#My!W<rP*-h(KX@}'
    'd!BtGh!i|)GKExSpwd)NdroKG3&x~K>uq3{S;e5q61f9gL8Ig$!8^kI$k2^*sjbyO3@R$8-#p2mt)Y~g+(D(JBh*p_+N8Irq|}=m'
    'P3#IL7GHdsE*h5b0+4_WwD*h}Desec7#QR&ZMRhzi}8P)^7$at8Ve4wYi<QQhvOa!S*4y2Rr>=(rrrQl!AUSVEjO|Q^9A{S(eu>S'
    '%sv|Z-|SOT1)?WfIVu5F?n!XXBO_FW&2L<63?ghuhVIgTD!eT;6JUwy;|6j|pH46QhXq{N%*Ln@)Y!|mfAq)B9}UhuyKA+($TWi>'
    'uR>tL7N98BkZWZ3b6IB2Y@AqWklMyiX77g*>}oAgBn$I$^&J5&qc|Dp4iBSlW-p)fDhn8r4SfL^9jahi>2UqJ9*E^rSH*u8<62Zl'
    '+s$1<>%pY~49R8S?-d6W4&85%a+gjO7;sY_33Di8Uu&@MPS%V@i0=K^Q9l7J5c0k@tBJaw_TqkjTG$izjOJ0U7(za0TR3JB^wA_@'
    'RIv5VS1}8}rHx)F?Z2N?L__M))dp<@+L&K>nP>L+X#FWBVK{(2f_KZw&TwsfQwF(d&&hPE(%Vvoo0j9W3cno1;%})^1OaS})}-!7'
    '`E>kOa)fKPw75M{_QR-*Xb;->E=fi_QFv<$W&^a)FEKDI%mQeiEP1T3kg#e5zG+;#M>ZU3rR$VJ!pp_q;YPgM>Xcg^Ga4o}yoiI{'
    'n%@X4v=jtc8C<|#aO&J|YD;y^3|p*<ufz4LZZIEb{_QG5LYkK)k7^dxf~3~TaH*#w?9uKxjcR;FDsrxTnl$FXL;>edOlr4Ah|WZ7'
    '%AyjjGs{)|tn+1EI7K<Tn7uM0<U_JD<_s8YNt4tR8y+v$A1b2@Plf0d+H_j*0C#~89b5~n(!w&;a7leo=Y_<Qc0v$j=<$>9wG$V6'
    'El|<I=jCuitiUY(Xc={xs8(8Y9d|V6BV4fdd;I~B0=ryg>tUQ-=3SUR;RqJN&XO>pDrTLF+K9#48OeF568_0GZf&u|_tBP_ijQ>8'
    'ZQuv!SbezIzez#$LxY6uJ`YS*B*GN_E+gAc4f{#1VLj6QcBnJ}FF003qwwJlE+)>M#8mp(D&L`G6cG(UMdbRa9I|4jm@9NzLXNk*'
    '!je^46l?uzpCq!=iZc$tGxcgs#mX)lsBCt&aPxa@adEuqq=H%h5yd^!t=%^6M5w|g1H@*ip6jv2j>)0ee|ANE&05mxx`f%IGf;X}'
    'vd?cDy&kK#z3fS29sjpnR~zluhr0XY=$LZ{&8-qDJ<~%1a0<f!Y_w!enNQ9KxE)g_6a*s<dg<_GTo4+84Tg_oJK857GeQ+Bd0uCg'
    'P4NAG)<WUJJsmRI&jNuXEW5A2Lhs@(t$LqXN&O*h#fkbL_Go`~{zT3l@3<Ombu%^Tw5!1E03`~(_l`3JonQXV>PVXq5lRm@CaV9l'
    '2mn0YQ+21Ua-`eWLG0nj(@Os?Q3JWSqc96p%O-{h^wb&tLT+q>?IiyC8>iwR-?R<tKc9Q!(akfR%^^P@g}eI}j(PO>C_Dl3?dvWE'
    'z<r^L8vYU$4ti84t@zH+tK$37C#V<|mtRffPcczoQV0=<qnwOxLec^))9tz)$hcuEH)bJeCH{a*eU~#n-_G`5v;Qy#RX`0%_ZQd4'
    '`01@jw!+(vFB}k;=6&L+5c3XueHV3~q7|l7s*|HJu1fYq-!P!&+B~mox4$)D#Fm0O>a$XGbgl<6Z|41(zrA9OY?nh-j5uX}Hg+}2'
    '(JHYw>53Is=6(guAH~Z<I9lC=paeH0@zK3(dC7nbhz%oLR8cKR9|Yul=<TyktoHAW%bH7A{%fYyHv~Ww&472<&i`GYY-n~#a8L3K'
    'Z%ly7Cb@X*P=ptbkJpKM1LKp1D!QYkqsgDqB+%lUJg0d4tMZ`X2l~$~uvQbpWewq1vbQEA*30D_cl-h(eKnZF(+(Q4>aVkmC^zAU'
    '|I+#TE^F1l-(VOdDFG3s6e_dIa#}l6d_IJ@h?>7p-+jX6JTmBoIgf`jG?i;vJ;u2rM5XId1w#fX1-Z!!DW9dONK|R(r@`5#1bHH3'
    'JDk2SxG*KLV~6TokPy_dWK-k?(9_K#z8=fLHYLAKD2U>4q|%so$mu?`*@=-C?~4EJ-)XL}&yu?illKusFfX<70oU3tC2vR}Mf~y~'
    'l{?{Z@a;&CpoK3J!3jiYdl&a8Gvs`?Od0Osy-E;HDPCY|tS%liC~!PotDAT6oWBY{A&K=Lt_{12N%l+g<!xaTRs__AWK?n`y0W$a'
    '|FS?7B}l@TC45v<4&4r?V;>zeC88JU185odD1tfo^>hUo1%zKhHp>4A=|E#GyRmO*Qjig0Hb+m2^eW2qQfe+KUcNxIHx;{}g<eNB'
    'hlqTB@?lmy5@_?Ss8l=6=eoKbA4igKkX*{)BjqfghcWfPCahIHs|5Mc9NrfOg<{vQmr9o<zgHni)2!%pMvNj24l-FB!U2YnBiLE$'
    'JbNObN*|*?U#0IBv6@ieiJePGT=}WBbaF-z5p~2|uh(hBPI=p8zW;=NatmpH-nwv0-HPBPI%>HaSsA0DlqqYY+AiF`ZM+84$5<UB'
    'eqpgs0R4WNl4hB2#$!*QkqX3~t>^Hp)R{+1DYq415yc9vH%qupp6B0%;kCXX_TepB!^Jhqln@Ty9$xR%>$Hpa*g{)Stee8eRfwF-'
    'iv_`%<f<K-4tK>l8PLb9BQ88C1B@zHvuy!oca%{Vlx@K_?%7tN#E<^`dG1(vO_v-~+*Kc4z2`O7Ad?6!l|ALw5D<b4Fl?*~5U@IX'
    'Cwh5IN$GSQ62RymBfyVt!!`MJ{pdzo?sICvaLAWKT<OJ9B{H+@wHGgK;X=&OJPEWQX(T8qq4OTzLya#u5G9KyQEQed2xpq+74W}C'
    'QtV4k3SmJnKaO5NcI8Ag_zjM$Ueqx;N(Gy*SCOap8P5W<duX-&a!IPA=gLV$iYo$YrOq`}=viu$-`}FkeVNgnp$H&|e12UC)9x1+'
    'i^C#indW`xq3M}HyD#C1UD4t|*fsgTQTQZNr$>RCi~_q~{0Z4A7RtpdStp%*1#P+LBiiV?cs$Q$#4HCQuvZvLX1t+s#ZoMvLb(g&'
    'lvcpZ9;Zb22<NVOhuI$)FFA#+D5OCDXG@~KgK{zZ3myvAK?}JhTHhJQRUBuYS-!e;tVxzQ`-GNz@6ft4{ZL-aeYuXP$Yqr;pn30Q'
    'E2nc&#ab~I9FG(QR0vKH2ZMT0uBR9b5NLQy6-oL0?AEdO>0D$NLbeg+IY9;cCH8_AX-*k%lQDhIY<LYyF;|?ZM2(ycTNu)j>*n*4'
    'WNKDa?FJBANLjF$f;VmN7jD4mX;Is*+}~2l!#oebT`<-135@yi3SPMbv4_dAc=+ON5yQO`@8d(5*DHXs{mYt6##=(y#4UXPM3r#6'
    '9T6catpL6O5CQZ4BaL5VRMH7{SNLb`$u}m_Y1R&1(=qN7GSTEU@Jg=j+CFLgf5o<EyZs~RfX|XO)YqVU`zrJg@L$;LH?ocacatn5'
    '-66Y$qz^e!iD)?}YU8w!q5V_Zji@RMy-L}~jeJX^Rul1&DLJ}O3Don|ubzWOn2JXl-&%i`q8u6+4pnv_+gjxBw$%{f$@<ttUcUHl'
    'iUub1y?o~)ROjwZ`3&3^2@PqiV3>abYxYjBoDV7^xapi3F}B6zmj2(X2M)_k;L0Ab)Oo03J_LsECqf%-?f+cLmEN`V34?&P1|QeV'
    'g|m3~73k@*lHHi@A{KE1qq63#u)g$vy0f8HYL}DdW`Et(UQ`;T^oO?pUw0*kk<8T<l&`ib)T`QTY*H1%6{{p7rX#3J5^IwybY8>l'
    '#TbA;l<{Etp{lqH8BHRp!|u*u#1f_SIWlDQ)jMv=?yYP=a|_=jw3Adb>m~+TDSzT-#VW68w`F-@8-km~;joNi#<%y=)AD@8g-htg'
    '+=HEvTlP%lma%K2AIOZ}%>=t}JwwP$R6k$?4G|p%SbGo=#j-D09`c$PlASkS<$;Gd{~*v+HQ6;3-iBhLKVB;|N3G4m>S1kjEnaQF'
    '4`7euXKXjUz@kz;mo3_+nRdChQpX)QsmyLM$bG*3^#rZ#cP!chxdiKG4#2Dd%whkG%8Ix0k9&fKNR*LER#A>U2WE2VnIKuqhntO-'
    'UId=mIo@Q!9|Eysf{UJLdLXLsOM6=3HkC`(yQVgZ4A>&g&<(R-VrU7CH+Rk%N{xTE{)n5n)1@^9MyVAol#UI6d0rlx-E_KSl*jm('
    '^zK5bLr7Gr>cb3I9OfddGjDkpW-AvJ1=c%C>-*6^DZ%;OZb>N`Mx~-AE1q05m6938qYBv4r)p2W2?&@~J7_d7mh(P79Z50OiYS`$'
    '>&ixYiSV^0KdMC8Z(nEc*R|B+te^NbHRKao?;lUl<*I#KHgUg7rEh<0auEgg%OkRJpe*3bgJ(7#qJEbBF7MU>AV4Dv-TyLnR53}Z'
    '_ck|s&SFaiF(EEXEV_yHEo1_Vw#nqe*t`Y=87OK8ulZpht;cE7y?xtrC?mG_E}Ba_ONb1pEmYXEW)fO^LFMCdhdn4xrK6uVfm9(^'
    'Gdpchx3s*!a1V}U8XTiA!dT(n?_(Wnx$Y)WAWD%4M`V!}vj(`B*&zwr#xy}6fT&vYzIn7!W`fSEj2^$KJZL1C!cg=DAn(D=Pn5aX'
    'D}4pM-5R4Gw%DSd*=egQf!{w+^l0v<j1dE2Rf8v{X{UtPIixl+(DNe~cQ!7iI;4M}yLQ2l03%V^SQ&D@7~2HE!zL)*CH_*V>x?^w'
    '1Zh>XM@NPQAci4u^dt&L?YEi<G-1Neq!<-V9pwNJ6=x$i`9Ak514VDk-Bf&f*ncOO+XSAZDwh?GE>UWMANE0>S~cn^M{PIA!Pz$='
    'lDL!KE`#!f{l9FlA0E|#Bzd?KJujz3#J}F}tYMJFE!;eijc3iUfs<M>GlWjq9X`3-l}P@n_K3YjH8gN1ZdBhlgQPA~DGn}hKP^9)'
    'i|6WNjp&~u(Q}iX>;fK(omqMyJgCvI=I=|jO1%+@LfN9YoptLsKz|GQ5u-7Dv&ahhyr)~Up@lZ|!%_RxB1E6=^==yFewJ`Cd@S-e'
    'yTqGGKo6G*&Gv9#-xx9iypEa>`jvDR&;{z(%Zf@jv7bF!PoAnbpw(l5eMW-;@`e>=bp%~@*2}9DuW*yX#~RBJ3|V=Fo6~aIG%)h('
    'q`tgs`I-QrEjK)oQ9R8^{OazEcjj(`6!X;HgoiE5oO{0uZ>qX#t9Yi_kwff+fu4s^Y%CuPFnV30Kdz8i%@O5gN*G8a7o<3R_Jn@Z'
    'n$@>H_c-z@zmdmXKicdSBWNu_(k1Jv-f!VLX6_2&UUHNQ{vj5JA`Sjk1K(8{E9uAZvs_6wVw)a0v{$d^Q;nf6l#5o!Kubgt<gG&i'
    'gDanHb>ILszBO_h$(UsCK;Ati?J?-F6g8fVloms6hO#mo3KzvW4jYmS)WdZL5G2zIWL$NfRhXyxW41&V4QOM|E|OpJ``Aog9st73'
    'bxYw55@({WB5dSrz44*xyc5S22FW0YASUJ(0y{XEHzmBs%9E9uoRHrl<AdpNJLsb<878Z;*Ma*0F2GTX;PE;Qk<q27A!KI?Yyms*'
    '@WnlLDeE|kY{~>9d^5wJ6jK`q6xNp+rQR55e7j0W?D3czD!8QOi_eA#xYTc_ZYHxr#aG`(Rt!0Qm?ltfA<*MA>uG^uGZHXp^b%db'
    '@z*7(l(UQxwEr!f(u-0nl06E)FiXclf@O%3Ftd%h5iK2f8W%|uKy`PR+R~Nk=f$X6IBZA^bsaVCNZPNYOfng%3HgMKb$(>~xubZ{'
    '10&U`V47bEEw1v&PXh{AF#6zih(x_WLk7S}NqK7)r(IEtY?34IvP%7;x$|y@&284u&0!QtkuoLDdY+wdF%_pG8bB$a6`s^;cvT3h'
    '8qnBy10{`G1b>?DoFZN3ouAg6p!ZRuJ=g!Yyo!2#z$OKytR7qS9<o7f?DRC(<AL?_qN+x>U+5*~QDN(%dChQk^4G|6palB9!N*kF'
    'xwkoVL)v%tr}O4+T18z$)Ma1R4}DCOBkN*@)B8=~UMiaIzX^;sD8?HM@bs8Gw3npbDx9J>Sx7JOm4JZ@$?^M9Y^`vt*|JRFeBrLl'
    'vF>#mr4?M6{y2%cv@!vAttoki=XP1-L#%S2sKI9vj6DkVP$}UP4nq@(*Mk!8@G=XMjC7hDVa+aTDwbO&|2*qxu+9fH=X9$^=osJV'
    'H7ckva%gZJt2miIl-2@jk%?3Ib>SS`NRP4LjW|;HN>R&ozo2K4s;Kp?$Dkcpecu54xU?t8mNdj!(=Q?U49HXVMA7;PRHz=0h%5dw'
    'K6<v-#=>$0Cn128#%xxKJV<MR<zU|GT<8y0Z?s11yslr_x{`-_E2~0q^s#HR@P&m-WP3`qsYAs$k1HRJK6lDm+dqI&sz_mUHW{gV'
    'TzRc8?(gs38B@b=zy?RAVk0u&34<T!gw?LP*Z-E1SD6{qL2dCsWir7D;yIGCYWFCId^HJ@ZDHZ#$xPT`)`^>zsdg&{NESw*ABc|*'
    'bami!O9ATx%Swp3A6F^Qi%g}khIUoXuY+EybO@$UMyOF$G#OAf7Hr4sCA>pvucs~=>Kw>c%1^J|rYe;r9Bwglu!PlDZr3W<R++dR'
    'KyjkGLZ+Qv<ETNS-9O;ahuSm6&TST&dHu8@rC6`B%k!i8h35VDUY6M?MI!eaflkM54}Bwt8wUOVTCy7h7Z|Mp1D^ev8++6Rk3)wa'
    '$V2B2jcKM20Sg&T`~>n5RIb3zbb)CJO&DggDCc+;T+;Kn3wK&S-|})RKr8B2bwyfNQj8$2G}S6{30_v`;`*jMoqtVJ=`@!{K9R4S'
    'l_6E=mIYJZL%313VMi)3$`XnH(1!#Kin_jW1>X?R`p1ud(xooa;aWAO`G4*Re?*r#0#+M%wW^Xl-^+D)>`SEB_^1PAD}YI@AWIbI'
    'xxnSx0DO_M3dvqWN2+kZ-0g4t4Rf7yFoHQwqW1wi$hN@^NNfn?5_+N(R!6=KLOzhIXGSf37}?@EOa=1l#)W;jR~}-!(r{Qi_1@oO'
    'RtO`L{DUTv_@D9xQ6?VfYz}7Yank{ePtUdvc|qw`_rtdviF=fu#mHg8?pH9~!!)AYe32Z*De1?+W9`pfxSEg6@e1K19U<MCY?C$k'
    '-@<I3*6jDjmuodc#?Bc|+^CZi%#CIyfx5Q6dX{hFNq@ps1a*kZ;G{BA_%CDT-+(}Q7hLA-B7b=c>nKU63>rG(V5tmIR4zsHlo(vm'
    'Ow!D1z|h99+wj2p^K-m}ilJ@L0&EtUIU2DfJ|NKsnkMYwHMA-`YLJzFL-tHPv>I?2EDvSK#S~pLNWGl97#1c#`ZPTDtXkdF1qW-v'
    'hEYWu1XDw4Rc>WJr5F<ycz<U4wh}^wFzGCLY1?KS6+3P*@aexa`Rc%T@Tn73-|sHmk!KBD1uVeZP`r{dhic582=nR!foCMzNlpj0'
    'J0&}9DLep&b9vi)MJsh*%bKySTWx3#2N&5_?7fS&4KF7nRp0#rSq6D$(oPS%=aTpYom$`ukh;l!!2bvQ-sxQ#YQKxJvQLTf`Mn2+'
    '#!|@Ojg(8zM!fRYpK+MV)4>B;?sMzx<t%TanKB;DGMo5?uh_rr=yUS3iWjYkI0b2yBgWdzjse9(n;G~au3j?<Y;*mQqGbuO6)Bj&'
    'm+q)~;6)oNYwXWsE-Ghj*9I@ryVtQhv9(7F6B8n-drrK~b*}aj1N!AjW@<lX@~Y4cWuDNBljymrkWl{s@=Xjx^E-<zb0cEi@YpXy'
    'oT458A^oPl1GqwBNvXwM4ROGe+tg96cY-+i^;259g6Y+D`G&5AZT7SW;M+wY)j=~c-uS}`7juQ*W+>0q>#h)&D{!c#ZiJi1_`NJW'
    'nnaG<pG&e<Vm>VnZBWPbo<DVP;4PlPx5PYR5oIDd?A{v{qyfThFc#BjVy)f5gk+~M0yQaVy8nepwITelM@Cg>G2-~N)km|^gLc^E'
    'CcVb<qCcXd5Qi1$cIparkJ&Y#1eLvhTJPVdTZb6nJ~))7_0c$9b&T#tI>SNzkunMsCtrJs?qqnEHo2UtT75gjTSwc;dH$&3!j*xA'
    'x}3DO<G=sC-Dy>}7uF*6^b6$V_(Z0vBd}ZqzE5qfvnCD}TZ60qNG|Am$qFNY?krrbyw@O8s{jM#t@X1xev@~SXc_rKa8_bV!4of^'
    'N!;`9)W(KE`M`skUV_bDF^KN9ug4&Vi<FP7A^;X;(u@{1btv?cqBo@`NzUw+sJ8#svE?1;*{*56C(7zV1~*kS`z;(jBofP^CS%b{'
    '(VartqhGCqJRSZk3wQ15@7IQ>*VEHspYR$qyMo0gaA;Hu4g@8%){QLfokmOD!6TKk^oGwiK}Vwq7F^eoX9-)`F6byy^@&mw7y>6K'
    'y1Ws*238ck!$p^Fw|BG#1&|!oW(PZU=MRb}YYd=Ss#*Pbw{a`TVdHqOx>^G^(6Ip$kG;DXP{<}fiSJveJ*Djko`1m{Xf-Fp3SUb!'
    'uRNw{>T`)snZI&E7B*_$Iy_M)+Hqj7fBCE@g6G}X!;e8lQ}T|XdA_f<F|Y-;=EJL_pq(^y7`8+~3-c?V4Qq&qLY%vS(d;fke$kmk'
    '!4BI)$+4;CwGdBvt0iMX*)RfCW7mv>BJIfkxzPx}^{Y}jbdAw7X0+KYjW|efs;*Kr)Y?#m4K;@ZPgGzXCy+p=)TVC5ZXn15R=y`-'
    'Y{&nV`>y&cCajEm0znYY_&tQ|n>F*Xa_Y6$h3vOT&z;e3+}t>Odvn^H)E!G-5xM2J+p2zSZ^K?z6j~t6no|P+lJUKVec#t-Cdu(Q'
    '$d?xBaEpb0+{(#(%F<9?1RA&-0Ya-{@H4_KrrMJ77<rY1kz@J;I&Ijd=VwZ(f1HuL)vdSnw0ae*!|oun6eiE_4F?0!{ewqn<z?6?'
    '`3#9kD_z;E=NZ<SAeNaux}Z$=3u9b+M_+GXkXIC1;JkneuzenF#-8U_M$vi+L5d(9;oXqDjI=E;NR1W{hp8IHkCizBQHw9Gl+$hW'
    'oyR#7jv9;V%O01#xQhtFDS*O$r$>th?lFxQrUttdsq{Rs1RXY2L}WU$-K{J1_hSskhu9W=1O~v@fiCq79>kGehy}x~W20sqHCu@Y'
    'ZC;!H-WlWLO?hbtKKlXAUW%W~d@dlC?lCALi6h?RwA9r*R4qKe%dPr*UC76`qH_c5Qg(8eJ<dbVa8jo7<S^Ap6V}^YIQd%uI1N4z'
    'O>O1%%Z1s!84BFR_z~W)D}RC|AC7ebC+5jz58~DNA>i&fuBR1x7y1L^+MwzX^~`xchC$D=u<I3f-&MAD2IjasJCUL8p7_!K40X!o'
    'ryM+AlAm|)@~>GYQtRDd19a}w0Vk8Jzv3@KoCT}f9t*v<#Id|D!n2&Zom9wr<*6D&&g~@d%>X}rFzeTKzc8(Q<+-iP1Rm<wpg^Xo'
    'yTFnNVlXzr*(S9k@L<l+&x4`}>K2L5%5y~p5&et|n}=_sV0J)h<lgsTiGE%?l%Om=A*_E*s)b>r`${zj+_bJSGySBdI!0X*ZfaUu'
    'Y%o9w>FsA!?E{-Ab|2LXT~WB7J4gZL>l~M6l1??egdz<yV8~yAD^}*`y3;P)ViNL%9u43<=XgL+wRLk>uCP2N-A9M3JRUrru8_gL'
    'fhCbFo!N}hbNt-Z8eb|&QzkIs;M9m>B_FWF9LWz}^A5tAch_Mq)&32i_4sQ27cK|8=n0*&yRq5DDH``eDfR~nlRF!)Vu=?5PL&>n'
    'FVSS_gq_@EJw3ZM=0hU!Bz#lT5x2Nz&K@eJZIH=Beo@2VQ82mb3!&p@KTmAuPZ685dJDpbi!w^kh+CDl0dXxJ)DmC0z>1vxnSJhw'
    'Xe$JsTf(XPG(bw+PyJ&T!rwg;>ssnd-8Td_TIpv7S5>YALLVmCzer6V4>pQZ{^01-eJ&)?dpc>_4$P%L*$V49b267@4zlkI5Y79L'
    'xIYymLi^S!BzZq9vkM(5IQx&@DSkNk$O7`D6Si{FDR*_rIg3vzp89gnM|B{0`13$u=r#9*ZQi+O--H6rOFbV)J?98$qd%?;MN7zw'
    'cA6z|nBtPBwTr#ef_;V6iq*O&VgDl%^vzho<cMNGzH!xP9dtX`(%zHqiiesFLJxZyPu6PIMBj;-gcLG?Aq8n65K_v+r%{vls|R1k'
    '#ePHSGaX_xk_(<%VF{=hIDQftG$u=(pizs1_|3Trdb)Hd3s*B<2VN}3nJE(NI~3>Ig*Z#y4!<?7G-WQ@#c2|anG1!si4dtb%z_j<'
    'smbKRr<?m6j|MtBvUc;TvnPCT*F?&fxSk-l#r71SPvjU*pMfv@s<@@jsW~zR#1u89FV4!%i`Nd#ILaGj>~*Lg&L4e>{8$Mhqq^rY'
    'Gyy;J%($X80Ne2z2?cs;asU91X~(e>-9dvGRTfha^h{(+#|bcQtaNdPvp<N?XeLN@Ed!-728q5V7`mu^B{&f7O9<%njnds8C<CPc'
    'cQ?D9@77vIF#{W%6KxXyqJsf6tcV5VYgPJ1@B3ZO-a92h$HJw&?(9e&apmU+@5cN7y19?xjqQZ$_+BHd-Kb>+L<6#@16iTyigtrE'
    'mmiv6S1Og}o|3z(R({+vVQhB4FQXN}5Yfios7Y<OmC#DMe0wX$1+zU-7m#-jX}3#;-KXG59;Y8(m!L7oYu2)-{uwL>&j3<J--|uk'
    'zPSvTu0j=+Fum~VAUCxUZ@i?PXK^;pFtXCo!8AZ=7k@igBK5_9ia1ESJQlApllZxg0H4-h1KZjK)VO;n0hR--FIH4ogk^`vt<9*5'
    'Pm(0dT#J9WDEhnW1G!RcGv%H3N>q;wvavJt8ojpdp{O7b?cA%vVwgy3=&`3DaB^g)6aIJguJ(mnohFjvAgJ>1j<-NvFMpo_>TZwv'
    'J7Y`amg1z8he7i_SRoV-hbI4lBd~vg-U{^;zufiA!d7-vlVB*yG$#Z)<D|)<@*bf5)a9<`hutRzI1WQDb5CUtPHZM`?|;d~q!)zQ'
    'J8XkdGU8;gR53~qMIY0O|0KSlB(XNBfY^=h)(~y;z<ZVB)`$lfIP`@qMbf^!4e$Rom~-v9a3+;ELy4YzL%%MRhUg(G#PHL3z4!ng'
    '@hYJNBsGIF%)0iK(*6orVJ98xm$2e$q{IquVk}rVdiR2rhL38W2)>P_ElTxZ;%OOUkQ^l0B%&W-zp$EWGoAcfKl;?lN{Sug_6E)G'
    'u!!M~ITXfeFa-XoZ=QyYSBB5biN4v%XT#CaB!bx@a(rk+d3`Ex66<9Eiats3jN%V-z+xz<Zr~IKf(e0ogyVsRliJqrwz!!0m{8Jb'
    'W?)USdI!gjik%lgOY38)&kcl4zueFGRb<r&+<aw<B#P(M5=0G32iBhB)SKs0nxP0F5kFVLTP%(mGkwPv#|o0iiARZq<-Gn241(wc'
    '>{#olwW}r+bjE#E$9!lW>k!~%TX6zc*f2I!YwJp$>|=^ILL!@}WMJy+yvWKrD~A@Vc0nd<Wy7cf&Jae>8h+v9+UCShCNNKge@szH'
    'i<|gzkBQt8zKg|zm1eQuqH3@j&L#=x$D_P$^C3dMO`8-OGMO%!eILzT$sJ?0aUG+afXdbr>V#JW4^t5HCI%-k_cPzwpuUClK%aXD'
    'x-wt_*Ra|Pz-VH#<sZ)}0g?`e;ceQ;j>=2N=on%Gc28VT-QkcUKjwbt`hwe@DqdOLSoFXJ5A)NZ>(=JS8eC`OEB7pz6e%S^;tl^9'
    'QLjCOvORPaMcvOZcuM~I^E`?f)KmEtpgY92r@<4H`EZDl)-4VTao?75!Mi&NA^Hq-K<Sk>i0;l+m91qQ_{-Y-U#y{wo9F-EbCQn{'
    'OzWgK2?j>QavB1q`Wc`wC|F3m;&G$+ZG6vLDqY4j#k3d^xp?qUJ<7I(-M7){lvhKW7wkTIs}EB!juAd%X(5+o=+?c5Xr50#oC|=('
    'q_X8GYz*mdQuwC}myP9!9eHIZ4{1qP76Yha)>&0MY|L7w$bnC0)_XI}Q~9U>RM!8&d7Ht>`fJi%+(2RFu!7p{Eok1)MAU4}bp)73'
    '_-k(7?0{qO@|LPD->#M7Br)%Odc-x~dHc?)QInYPQeF(|x#m@KaF#Z+Uh@!sc@8x@d)alzd$kzT=NULl*@v96yqZG>S6V5+J4N(('
    'u)dbUxp#(s|BB$=3crxN5#}5?Hbk~)K-4xdm}JU1p`wYTRS}cLh8TW6fm;T5482|Snlllmdez-0BKb35OZn2>w8=ZV&FNUtvmm<6'
    'xh7p;8fOg&^toY4Hmgx*9367pcYRN;Ky)DEb%PNhGxk+u{10i&>qJ@w$+XT6a)(*nie)nSv&1afuHt4>+M_wZi&QPl*T&Iqt*3hQ'
    'Vi1_`DNNSBdaTpj08c8ZCfw6!Mq96*%*qqdCxA1**hnDNqWU2r(L)S{L36tUY?(|r@=4K|<L{qD2mQ)okvdR8cPVqiJEetdPa65w'
    'Jk-Fz*N%VAwkL5iR%Bx*q9~MykQ38$K0sTHk^g01C~TP!uN)q*UURAPUBo(Ntg?So#t27}F3j_$8yV>BE{}OCqdo_HKco)&0OlEP'
    '$OhGqh;a5(YLSO(UlT)|bVXlEBKy{yN*Q|{)_^_4d9UJ^esqcT{a|5K-umZK9x7q9`UZHh6n~Ggx=mGTbzO6(Nb3iWz!iN^WIrVV'
    'hthvJ<^YEgGiq;J^p7*U=<Rg21Mf0U+W`O#9O&;_xLn*z?zP(+CQocm54)(DCM9KklEQT&O2nlea{+ayK{<N=OJG;RLP)+fndRON'
    'V5-T2@mG$EFDalda{dxrtePU``7XBw?Lu5gBMnX<_U4Uzxt0hLDMbHYEKK4C!n?W`?~Y7Kxl2UNKMRT$5~Keh<G&7&_>^~JQG9$K'
    'W2VLjMnW7fJHygM>7k4Un)55X+ez%{i{8Fi)OK7Q_yn(p)O^r)_y707D=#3sBc@Ujy-dg&w?Da}tcfTLj{|&pnE3m8Vv~s1(PJ2y'
    '_Igp!@Qv&Zk>xM+CXLt9h)q(_g$Q^(4y{3=hO^xZlO%1+((9QZO5q$@J)P8(xhGHoZlqU?uK-+qbYn;!AgU~Y*i+N&4jW6JvK(^p'
    'H+l|ore9y%s|(!SEpIXIe%jLl#wkFeF~=K&x}uLQYF>ev3FIIj_HG?m+MX$TU@|H+;`IAMXn{vtD*~oMPY7G;tV_r*ueYBM-*C9v'
    't0(~}d=RC7!c#j-xl!QmbD5LMwCT*IOc=N06G;onh9u1}w-pi&)04}Rzm3s8@8TwDZga0B`?NpUo$UReD9pXyHOSGcPf6Sv?om^}'
    '*Lbf&6>KlP9tiyte2=Q>TS@+2g*od3f*^hznO)*RWRRvc$GDZ_5aXtt=qqqBo>p<LmnhGCdlO*BZ->OcY`Qu^pC8|qRuFSg#p&Fw'
    'D#g*5DyHljVaieG<&rZb$Bfe=JSK87R-5l<S|)zI8>mMwAF3+q6Ewa~Zw;C;!-~LLjz&%&a0je5Q^@(u>Q+XJoGSH>aL`9qr*}@('
    '9u^X60@1K2>j6aT=-i>95sj}^cd>=lK?=#RuDAuf#B12J<BM1$#w#o8y9fsz1gV$TEID(Jtek?YOwcSBv4Jxe;&J#`*DsKz6<ww}'
    '^r0WQ2<(iFH=zKQ9};P8dPAr|E)P^tSZjkdxi{-$raxT)bB$JLg>&~j{snBX0M_6MqZ96PEq-P<d~uhtGFw0?g+AF42O%dev_oLV'
    '0};L>^*#sYkRc|3Q{fC|QSGXSZOtc+-EfJ95Jajag2T}LXLajhEgzP}DFc)oxMycuOx4`%ny8w_5aAlFU6R#;VLsaQFU8k5hq0ZA'
    'Qe75v-v`mQHs|u_?vRq9#Fwyg2UK_OQ6NbFQ(I4v<&S6fyQ<clw!-m{{Pgt0fZZ-Ev$F{#-tb+46cSmLalSX%IzYG$DfutMbM)+3'
    'Cd`II3XOI7z?;aERCn|FS52K2MX%xvOI5IFcCRL4CE$6H<Y<dWg!9GPvIxT+S59nWNC?lZVdNML$k2fb%^f0+ejyP%aL<(3@o%Q='
    'q?kUfTXXdoJ%iH`WOu^WwQ3RavJc0la6tlk$IClmNFC2K7igXwcQfS9X)CW}hUTMiRK77D&KVLV`p*(h#(D8_Epd;w+|-V9UuP9}'
    'P8voQ66>1A3j;$g%=f5h#Hza@Am33hQ`(vfgNnlKsD$<M2DQ|s0~+IUvA9`g#C9LC!bROG<mOyBUB|c~XSsd5PZ8nm8@rfEW>Y4b'
    'reas6)5hA!rNgPIPRYMkGXIYZS6OnjaQ&U$QOx@30_315TpgsRCG{kp$&Xlu1G(+$PxnbDZ|<<hoI*7ySe^EBp1zWHX~hS(C=5J)'
    'zW~(3CLU6D!#?`yTY%RD@&f3+nUeN0&u%T5_o8|qm8Gf1P<J(tXe{v`R!gD~z1aRM<Sl$h3pX&@-bGPXsiy)(C&qmzYH=KO(?&iO'
    'fPw*zjN=WbGuKWAb-$o<5Y~Gy0P9L-2D*+^X=inSN!U(Wl-M^!3-`@8?=~El^bO-fE!bVM2`oQ6Rdf=<T!oi+77;$$;sRh$RYA;q'
    'skH&WOhCfi1y?0G=#(*)*_>(g%`e#?qvWcNHdqm3$WmO0b*Ix6#3~v3hRH9E^X{HPjj<OHx*B3?f{qNng!5_pI4T^U<{M?{PJJCI'
    '=?6}mA2Ai@-qtr@#s^wsDzJwwTXE(d5@(IZQJyVo7-I&XpwWpq9`J#MqCvkj$X;J$?YyRP!2DrU7|N$i!i>V)oPl;$Y4(vi?JFiU'
    '#!EOec8nWx<Mm|x<pp0QE#t%FD*?zT@uGXfkwb-x{CUapgGP^l*I@pZi{s<&{pvk1VN0MT%JGwW+~s_kT||G;fl|Y~#ndAQqV=%)'
    'Mj8|X1yQ{T+=sm`aq+(2^_=}JZwk*h?_mPMmd8Ib>cukLgw*g*P%k7B9u)d_KE_4xxRE<upT4sv5<t#TlBlx23~Y%}p*0BZpn|>j'
    'i?q<}P05r*55y?CE-vfds7UUXr{?<A{b@Eh=W?kbipB`Pu~QHdwznYE7rFUjo-(LyCaLGEjBQ)$eyS|E(+?fC{hT%c@xszLSC0Qn'
    '@FGS=Uqc`{2vKarnMz2(O(AD#k&ruqP(Hp?3ax2A^eS~fdv9sN#R?Q#*9aMQPV81aRvE|ITHUvrIVz_V7(QluE2pi%tK$W2w-uKU'
    '3nu>6HuH0!9t@q}h=P1(^`VongTPiTgPVD*x`o^{B%LRjG6Y5W7^mCnR9BPFQ^6pHVJWguRA-hMcBr{%dxthl_>vh;-tbl<$*Aw#'
    ')IofYqV|hRkbyYcdxcjsv@&8|vj_}M(~M_4zGqCBkusZg=?ZF1Si2QDwL&N9tdS|~q(zXz#!G$zB13XxX~hDo6GVO=`T+&HBu9JB'
    'XupAGHyw=8HQqJpY_?IK1pb)ESs^9ClU~!__ia@^LFv$(E#JduArD?~-L*B=Rh{kZUueQkz(N2^Y-ht(4~8Tg$`uxPvufqPDR~+p'
    'Ro_`GxZ-!V$y~<a%JV&GVZnilnP<zJ3n*Lu1kQ4RW!V7tokZG>y)pceNyd%p8KQGQ7gw%zQTIl_5uJs=5QP(Uz7ZY4O~xx%$6U3|'
    'Lm;KH>Ml8|uQn7Kt79uAh8d0=mfIn9l4C<^xuYdmXs#8gbzQzZ$Q(wbkv;bDWdjF%Mya2Qf_$Sz`zTZXEu$nLbw)WsW<pjPiYqQg'
    ')Az4aVs7)D|GL-VhQ=*z1~|zZz74eLnKkJD;`2A-e6M>7xDwb#VY#<rVroo-aY-jv3AR>n$=5w9+{D0&9C;bt<-_8g%*v{IfUiZT'
    'TQS5qee7YkLjnjP;fbmPKFqf33;eoeiQLZ491O`(O@#{2L8;=d$e^WJ*L5$i0xoaF7q0h7UgeclF~)VGLABHl>E<KYy{}tLJH@^l'
    'WxgS?M@3NFj{4Pk;XRIDd3R3*nskrm<xQ?jLYGVF#*i~mG3#AzeqT>kA>~OsF-Gr$joO_Gq_HBE*G5N(3nd%Op~V`_fu|B%_-D5u'
    'i5K%@q=iQd;CxR0@^)PdF!ansA`$4c`%c)+2ITsS=KcbAvzCyiFrX?jfp)2+NJgXbS`?HB=E_bBlsjc)LRFdzoTX{#?tt^RZrA@&'
    'R|Kq2m)@d{MhhY0Ftt*7EW6+d#!<m0C)X~+MyI4Mvl*}$HcnR2$t*q$gcdaY0}a%k)a`DpKMtmZYYHhf@r%uSKS@IqZWue8Eh4Yh'
    '1&(Hq07UMGqRviQ06&xi&PxU-EkMuTTMCL*vy(UD=`*qhuq*i0wbLi$Xt<F_8R}WATL#lSJ~9zscn{_vA#q6&STag6JCXS5R)(CQ'
    '_*WSVg{Asuazn`BXVBy3&TT)i#1ab;83=deCos$xUlW5QyhqCZ<Wr-)TIb_c!sUuD{ek{SS3=sVgjyhkU{!>b@TzLK_f4uNU+f-u'
    'w=z;_wAxb_Bgar*9)GyHgC%1u<_EOnehgTmy>kgd=D$+hPc`9EM?*74$&>DUS^7h<O7=KgWR8lnw?)M}yM>@LouA=|^e<HJhn|if'
    '9Ik*2CnnVHIic#R+haV1Z@F2Go?-F|B$Hd^qm+EoHzL|*NwGO(JmOV}oY5J8h5lS=x-~4}^^Yl+_6|v?0b>gn7`{4%TKGh$a1yd%'
    'R-hw3+$ozgr3GhyD_Bcsi&fXtfnZHfhmLN6vbujwB2DBQe5+J#DC~6S5H3#MB0)oSl!WoEC&3}h0u}Vcet+WM7AaS3RHJ7H`um4x'
    'F|X}1MOXdk#5F@T!BE8JvF^8mthIX6>$mrGZT9X7UoO*Bc*jL<8@HDGco0=Zzjw*c|EK;D6iAe&GTlqQrJis$5a5ZSjQ741N!l?h'
    'y=ngjx>SB({?Gv6bqoJHZMZMJuONd@g98#%O}*W}ymuQ+Z}fvRv?$;V&CRu0_}J9xYa&`8_R){mgCDzFEdyF9Jq&939Myvm?&V1='
    'oh{Phoy^U*<fvVN{Zw&E%p2~^yQHfQVqep$RVF_iL=<t#`v8E0wTMl)Q={^GpL#w=vQwZP2S?<N)KkM2f|%ZmIWmHmCZ_Vvu*jj7'
    '?!{T||MW5iZg`|pA&1&-_E7SeIn#cZYnoLO`JV8~q3$91cKpnhI`DK+T2%p%ue5-0XTm;-GCPCgiBPdejRMfLln{pX)leLNb(H3|'
    '2j^d<JruO*eZixBTk1)ly!l)S&19n1;-p|bep_IJ@URe}az9Nq74D^E|47lv0c8AVd%bH+6ZTg}#gn{(<*omAN?{{!RmZ153UyL>'
    'PKOC*=YYFV<1hD;q6PDIK-qVU_Qho@t6W$x!x&12@mI@-w4NV@6LoBIjagsWxU;Ux*|vHKdGhB%`_TKPS@D}&yX@qMN`t$<0u;d1'
    'RQn%JsfG3(7Wtgh3{OU|r;P#iJJ|Q1!t<Qv1YGnTJE{!f%P2mIUSELl>W;fp4h&!)=RsXTde=V*ajavG%=Z^Z*m#7@y=%&F)kLX_'
    'Mcqj>a&)%W0R{EHGVv0`Y71_qr)>)Hsd0xC=cA#hE#Ur&lU_fjjzf(20)f3adjt`Eq94P$)j)76b;Q7gr7QZ!><QnS10+2Dx3VD<'
    'YFeS=DGGK=axazGny5!?0~JT%+M-VRlA)l=w8VU<jd|&a76LjtM3D7a>yJiMir6wplnS^)_ZT(1%Wbc;*Fm80*?w;jyrX45A8MmM'
    'V=N58J3-Kd#X2*<l0*hM{|^A&IYA-sMqp&=HJ!XQV~ahD4X7y#r27r+bdmDce_^eQ`K<?L#1OJ>{cVhKbG1ke7{*^x7?|Q$PT=nv'
    '6a_kVrRf5AXac%Y)<{@L?clwoTne==LVy#Jkm*Ze&lT}S+q4kSGe<=06hATic~IIJ^)LR~K^q-_I0);F?M8S>4peP6iEv@r)3(;f'
    'g~0}LBIo9RFGK*l;7H%pN%wr5FMC)n1D>MK-9^<I{{^C3nf?*rG|2TFrYXT!zB(>{N)H8C4^F<2^DuSQ4SQMl$+#~wwV1+Ak~sk+'
    '=G_kc5T~bSIKJ5RdMi340cJah8Pq|V`1^1|t2eQ2T?pqbdjxlm{5G8_w?=5Y=t9~L0|x$pfKpu{t7So`q;>s+pZ3?+bOB|;XPglB'
    'k+j)k(PP}@Mr{IrcAo+4f*iaSH5hd+6%GtLpz{kp&!3qI`Tdt=gZID4$sm))i~NG^gTaNo%<gD|Y>@_pI9vZ5Csa#~NV-5<;;7o>'
    '^$|9wBvQ#Y)#38I_4*=MVX-K$gA?fhPxxHOZ&ykAbAML!@(8{Sgquk3I5Aqy#u!DtuvNYpFCxAC>D;F9GAshLKNMlMQ7(*-Yhj!3'
    '`B6xh!e8`3fvEV45En?a9{%6(5v59%a*3^$=TF7jhRJaM1zlId*3HR6A3HDyp~Z04!S^!Gi(BLIb)yy3A(+cur<q6c1jze#{zR4+'
    '^Y&Ju>xbdPVEZ#X`lGzVO^3ngvyd+r4IIi6UTpb?ke`R5f}ev@;N%st@cunkJ&v=!>n|)~ggv1}pjN6;M-W?C2;jO8p%r`kC1c$D'
    'vK)n8DPE*}a7TEpA}ib-D_nO3Bey350<@aI+a|c*?4Ueyp)hM|<9WDsga9w$CnN9K>b=+%yZSYOgO*)rCHi(cldz$@vZ84{HQ}lV'
    '{q@AcF4buo_27?+d>2jezKv8E;mBfTp!|TXC?q#AH*O20bOi6{dcOk?g`C_<rWgQ5^4i!-8i*s!SttS}v_s>s|6-hcMEdT(%r%Bv'
    'QaNgGViSzr)0^aAwT1hWae|7Wlz@EfyCIMtdebRZ<nxh)FYJX{Md|5cPLE6APr~T>Z}c|~>@5N{)@Wh_-o2Q+Rp7^?D}H*AeQs6}'
    'ROC|5j0`VT;NCQc$Fuy|sT|`?uLB$9nurqY+kV?2<5fK?QuCvx(Jr^QnV-BJh0;vT0+4nE{XHbX9G~9gWG>f+SEQ6MW-0xSxhHwt'
    'H&H#c%Sm=>M=A@6%xVR6u8B+$J%G=8#78kHR|wd}eMq__rtcEq=96!@2`lsXslK2%wf*({?~ub16*p^lhR>w=T$U!$@K)aJFmVs#'
    '%7huksMl6M({(KFse9=C`VxmOkVoDO{TrS2UE*u#Z2$(-9|MgI(*xC+7Di^*B?$Q9geR>`(sNy(ame}-xF@oIR7x=frChUl1ex|3'
    '#<+oL_>|q@LKK`ALEv<-5G}vbV`|7$I2jOYA5FOE>(-7XUPu;lDzTo!?eTn#mZ~V;J?U$ZEqCjpkk~#LI#9rSQ9G895K!S?w#adf'
    '+<3W?)$4N)SnZIpNZTKgWnmqrygcdd`(jiGrZzSr4(<LDV*ro<z(}Nv;(~O;QQ(%7G3a3j=DLr1P9{F<y&b!au<>>wr$60e2Vo7}'
    '9nNj_I@~`HmpJco2+Jveyf^zK#gVW>LQyS%og~%5$UsF5eQ8Ql(k@wM>bg2#?k4pd5pAc)ph#KiuOkLi!RzM3KgM>obuiRyAVUxP'
    '5OV4z#~!m~0AL+91J;t6*kV~A2dM#?^~+`3I?<-Sx6XYlA{LcD#|+=FaoNll@*E$wl+ck_S99UNFlq)Mx4R^xA;f25{g`t`)M1?@'
    '5l=*Fq#+<NEYfhU8t1_L_FlD-%Zmo%So*9Nu2uU>>c{|T?)k6yF`{79>#8NVV(aY$UN{}M@yI@+O_)ABgE{|(cR#sBvO%hxETUVF'
    'P?NDn98fk|xz)bNSWtL9g(0U8^~z3fimeeK%k(Sy8a)?Ym=`=|=!lgr2`xD0_`ft<Lkk00&@kSW@u+$Ze&<;TSD@Z&!7c)h*u7~&'
    'E2SJ^P0okeuXW-ENFCdBE>gWs?6bLFQ~D-D2zky41wv=Uma1cI9vg`i4_L%%YsrPr1Q4&JSZ4f&{<m?k<}e~RbEAYb1oP3zK#8^5'
    'ac7biKvMVx^X<l6lkjW&Z#OX#SQa?n3cb$SNAj`BEIPPvNJs1$w^Y~P*pgC*D-m2sb3psp=5ep7hQT-+SC>F@_ryt3<VT$#vW2Vn'
    '(pO*zo}9<S5*A4Rd<w6`s>QWg@~X@f*nf%4OtBF{2{;*L72!nbkw22_*I{-VJ~24>X0F%huOAqOZWwG{!gXn?ECBPS3<v}%;~OUM'
    'l0YyxE6#y7$y#`5Fi(#QOC^~8(m17?%~?>(Xcu@p&zEis!^fJ91k*`HiQ%`$y0swk1R(Z+Jcn?VGa%UDuiXSPzCL^Q^~Z$B#Wn9U'
    '&Y7}D$-}M0kuk6003O<_mp9^oRf!gNL9u)>M;N7tq-OP5Rq!P%_FvErgF~65Pu|^z$EH89hk%;vkmPYHTSBO1PaBF~gGHY(P;Zld'
    'b)@=g@YK!8(u&*OcQ}(BQx6<RxVW+|o$rDf+fGI<F{w<$qF`$HX~?8;k|x(mBZrJXrxvP}#@OAYSTM5(=Nmyg$VszI3uoxw7A6tj'
    '(>dP9Gs=F1SF)|by6-8Ihg=lh_5aZ2OP=g=i!_czAi!UuF1BZt%XJ$Bxd~0SimdM%0__vXjVZl<SSS|?59tUh0FoRSDzQg#rct{O'
    'aBruI`&lGJ3y$EAA@b6@5Gk{EtIByN_Xz|@PwBxQs~m^XAiYBhG={?V&i`b_J!?AV;lK<yS_<3J$=~b};Zyix|4^>8g*i%>ZeVsz'
    '!8xN|DN}}#E~pH9m=yW}MI}=!;uOjXmq0`0H2;z0Ov?3m<9NH1k>vaY8XAG5sgS+Owb28hexNsZ9B)l_Ht?;Zy>VP#A+WnXKIGFp'
    '3gHF|2BA{@Kz-9p!kDZ+)6PeXxL-%Ggj&xh?drX+0$H5=Z~~&({zMgyC#z-pPB5&jh<@)VFij3dRoPjQ75K3p`$2t=-39(uzIhzk'
    '-m}R?COny+dtRxsj=yhuB;71;<HJE{v*Ni6tN9==!`r9xp>-~U;s~Tq4^QEB3rqClu%{=RaZFe4ZeQ8p5YQ#bI)LCcUuQTAWWC--'
    'Uaep=k?s0fvQ-2aiaH?cUpE&FF5$F^u3Z&S@JTv6PGd8XEx+bfi&VS+USgAKqPt2BYC;oRT>f&jUuP^&ben}0c2VIQJyXNC@9_kV'
    '1HZI<<QMQ!ZqUfEZ<?G60YNx^u~)hV1W|_*=zU-f#(G@a&W*MdN8&2#zDX3>U^XnRxdiB`HE#bQ=~Q%b0j!up9TcxpT;g<?35hRU'
    'H`N`{P`vkexU3O;$VDwdZFuJTWwM5lF%<jGdEwke#{ztDGt($-A^frWuF73rGNBPK*L~6y{2N+WJ+OA0yZNzK3ZF6k08Mm@Qu7FP'
    'rCmxDPs`n}14wVnnj{t8lG$m^ZDTaHoGnWMHyy4J)n3;&x{T*Qsd&Qzee2|eoDb8B91x{~!ajHIv%9kBr~qpZ;c)^TrfZBBd8^}H'
    'ZnJ+4pz5&m&{J^TbFu_qyNidqM4xR#X@Ibjn?kO>l^^c<O8N5q!Uw}_ynyyGp~nwl{2=`BYg+1h&2XJdj*iHglK!~cD6&8Jv2ZVv'
    'HOX2oCs)?B#gW`C;F`kH9FDjN-_&M{{z0DU)FYcq63+T=Uuj7a1)CAHKhY@EEA^rnkv<71Q7ZbCSs_55gMMA8C>H#Hq9<K!Rxx*o'
    '^^%s%wM(;nAnBpp2Su{u64Yj(kI#*Q0Q+yA1P+7OXc*#dBo*otVY-fHeB+l(!6`pQnjJjXt@0ME=qYmo(hfl7=2XJp0-(H$JpX-^'
    '9^;FL*)L8-QROZ31Yzyve@@?eb9gL04U)M`ZfAWLpLF9P{UltxKiLnaNkr`(je_{5cKVaXGBJ{CK$>021l`>iop|&u(a`I%W2B2P'
    'D^MA6;QG76aB79|jSeyI%&&Qf@s2%0w^h`Mx*5WL&f!vP=_G!<we9l2wcPAT?btwpfFp}qTJ#*0%JgFV*nL`r+j8<ONL^nCiW4}P'
    '9)Z&sbTX_PV55c$6%+B3*F<VGBeIhOxY<i2UdJ%F;lG()JE-k5@QT%&GG0Ma3(IVGyhyfI1zI{bK>kz;V>+@KGzwam6~Ad}&YwO6'
    'R&Ut)XR;`9rN@10>0Kc-#%1gX#vX+g%K94U7#f%LF!pWDWO}V#Lqpioy0%7^4FZL&aLn_rhoUrSE|8WT)biHvqy!_SNM`xd@IBJs'
    'X&LKXL^J(5e+mdxT%^D52i%O)%6=lcb~6F9h!c*M++c_~o$}%NBhXlCG#=T1L{hTRI5k<#`E&qGfjjo;yBv6}b?X7HPYHJLM)`i-'
    'lJy!Z5gf`%L-!D>fSI-%Y-1o(E>C7L$d<76NrPgK0XUBy0F2dHO$^eS?V>okjrhJCRy>sscGQaYYhUz>g?c?BDlLlBa`}CIBxVNq'
    ')r*G`PidFG{Lregj&T|#ihq&wc$AV0+w*-?OT=QfKK(cb7oY_Vnb!ijsg^Ht&k2l?7O6OhV}{%h^&|Fl^?Oj|`~2Glx)PJq<iERy'
    'OwMq6V{a$+iD&aM;V8rC=$qEcpl6TNG|&y4sj?l(V@EJe8#*pDU~Uc`=nzA1wV}D>iE4fRJqz0kUcaLVix2hV2|$Ien~~)1bWanL'
    '#+KG~3bLrJC5d0Y-7TLmRK{T=VXl-AoQxhDbJhqdwheX{0sHnm-UDYdZOhL$dmilgq{GKC2A63ho2S>ccQIjEt&h#H0;w2GL?mq^'
    'o$;W3CwMT?B@Q`alFmsReG>YW75js%PwG>Z;o~|Zt8DX9kU{iD>(-Dlcb(BnkhM^eS=36&%aocUI>3^Hr;1WK^ov)hlIKoJ#j1$q'
    'A~kNW?0?GL1hY4Y@)X$YfIgF}d5}SZyglS%h1_@;^?9vwJOvIx+v##AC?Zs3yxHd7;YI28dL#8I0zIZ#gt^0@yLKmv#vgyQ6x^-3'
    'Z-8gT+L=4{;LFqd>#%|mUsFcghLi9N@{X3IXiBsWgL64dIuo^ulRsW`pDh;PY2t7o_o;j!I7Br8jAU8OtV<bUct9cz0Q8}-@M+f-'
    'Og=ZL#Fg{(sR0~WTqNfYF(U9VI6{9`0M!E1y!^{J9OztrAFNR%C?FZ|H~+Bae+x1}BUaDNARcCq_Aaw6uVtD~PY%hXIP<4ZO3fj4'
    'g@KhgDdrs*)L&c^in<DALN}_G8<}eeN9l|P(JG#}?W|?QDqzc|3oQ#a>OGpUSY!0M5DcZX`x7^otKC6U{P!2KBU0QFDNarL;`0e-'
    'Y^j`k=9Qnd8k8jK6wM!KtN2D=$ZVBNk_pf`sMWNG7r};l%;&!&)^YS)?zzKZGDg<Z5`$>qGE5B+nMcE9<0$GbZ&ex~^qV{?n^;AB'
    'gXMV1R$Jl2x*piq9azf<A8XY{z<?rZuXA<);6uZXgohVY|E%cEcf<ov$8hxA^hf|oyr7g9$~A$)G2#aoeo7QB2$s$<Z|LKxv;_jv'
    'SUwegd%P<X{GL2sRV&v|dyZpd;osqZJE#r%l5y_}fk}J#b@4-C%=!<%wF{R9O7UHw@9Z}O1=nQCY+p6Dqy=0>3K>9(W|&}+3G|y='
    '_8zi0G1tn&$myKMDMY}XTps<^cgjLL$ndcfXi@<|QNG@4rJ9VfHPrzWjz+n_s+w+_6;As2^EL`_6tx&<jow0>5!>~3cZ8&i`TBT1'
    'eZ2^(?{xJ<VPg)%7*`bZl0~T2Kj@)UYVawAPM6~!V~#hi8EOvIs>9Ak>EDH)0p{ZJsmzzV$A-p5(0d&}oS>HTR)YegCfbz2#519P'
    '&A9{#o;!Jtodf+zGmIfNg%=OyZ^%&oOAa29z1%8s3_JUDoFJ^2$`_kt!R)-qq|+u7KwhGY8ROm#(s@&D**@AMT@j={rl>idL-=Mg'
    '&|fyYKg4`@6%`8%38U-7uF>sciv-0-cB0{Cw^?q0gi499dw;4;d#3|gf~`W>@rj(VXERNV<oyy#8oc2g<7f1e_-vd}U%Fy3m_alp'
    'hytK8FWn8__=z3vS*;t=`94z?a~5#7y<3GDpN1s>$l0g1M6>PF?2^%%l3(@vy^!H*QprPOPT4QMl<AD=73GgN81Kouycgxh#N2aT'
    '$@r@T3%L^O_>;dih*|qjUWcLD2282wUlVjof@HY<c;iaR9fe+QZTUqI6aRY->ZnS+r_yeDri?^y8I7hBh#?aJmIhvbN{KOJ$E_*!'
    'S5rsA40vK7!*76vl+pXf+TY|2o-q(UuC(a90mx3_mG_V3qwH+=**Mk7sE1dd>8}!!gMCaqFQ^?Ot|cf1S%kfXeAuhKN_a8oz$hR<'
    '>W+c5uM;z(BQLP!PggE>FvTR!JcHHzJt@qYE98%Pz^0RD+1<O=jYmzH?hcyD8|C!xh>%YMHflIYxOi9gjbF=e7ZBGUxSG&URJnB5'
    '0Tzb#S-0*XVY{lMghvHhp^3RbNkpgrZkynKNFOAN#BWm`-uc`mQN*CY_lS7OMjO8dw#$hUf5-I!kIG|1lTN6mPL=ONXP>0Q8t5)d'
    'GjLB|#K|>pWS=N6Qni;DecpyfHntnf*QpiFB#tPFW)f*nOF=`9U`yucM@6R&{S?J+aApT>Etgs(rtB)=@?Mk!3Or4DI!+RkA#cY|'
    'k-+T$!s|g!k6^DBl-N${l~}c|m4M*{&kd+aDMW;xxsNiC(;}TIcRoqeL3R_1eKLaFv`i>{#6=aG;hujcQqwS6zPd;;P$wU!iD``r'
    '&aZU0FG1m{AY_(yvVL^nq$Zauyq%G`UP?EeQY3xS?q(OyVqHt7JND3lDw8^5{ycUe11i`|X3oP|3nMd0Xe4UjmN4ktJMLi*Fu@I0'
    'F^#sQCpeFkXFso#t1KasD1kh`9X%5SVKgLmXea~bK4kJC7xRcrcPQ2q`LkkXndxfo7221gQ|@=XZky8BN-Tnj)lUTW^KHyx-&$cc'
    'Q^DFLR5Z%j%rkH}Qbia7*28yE3pVZ4?eEgX`koU01GS6LqkFQGw5z#q_Z2VE6P;5ZllYv)`Bf8K4Qm9QH&Ios@(YnW3E&dV$6$(A'
    '1YrV#Duo**Y_>F!(ppva4%DNnP*HsZZ373Pv=4j15mG)WboOP&rvw&tG-F1b8OkJlQinBu4KmW9E{+%%)51JbYe7xqrQ0X}^Oq#a'
    '`jb^5BNAbJ0GGH)xrMu^B3AY=?a0E4{U1^&7mRrh<h4urY5w_bvQHvuP}dd4DXc>60(lj$JX>=C-iDW<k8s3zCfbHcAL>pRmNohb'
    'A@c*AR;u{YkNE#*9CkbZ+O2}5AM1d!y#xoT+ldEMp%-P>rwR@{Fyk8nzIz3|1u7_r#T>r(99)A9#mo`UL3$BwN%~w>iwxE_b*1j<'
    'QG)?&0&GFCxzgY<WU-)e-R=bqYwzQC(_>$#t$P=9lA~HM8eExX)T9qExUNxS5rY!9o_yuFdo*7|PMwe+uViV;#Q^#g_SuTpD@cL+'
    'jw}?XMS{$OuHd5c-11f4xtyiTJ#yj#TZB2WIRyOzngWwEb5Ca99=oM=cn-^5p)L0iwuI&~pRm@wLP385v}850{}kA$P+P~9DnMJ('
    'F!to2-AXgnb$bv;rJJWA2tZR_&De5YfP0>{_4b0&GdmJSf{M7cDwfnp&~O$mU(hjY^y5{T`oUbnUtYMwXK82Bvv_S<$-dGT{mtl1'
    '>l!@KKp!r^3Z`!vFxYWJNG|sjASlyE-6>%LrQ+LwunGA<mbh-uh*b>6rt^4hKX5WHPWLq5NGMoCv@WYJITy-+3_&r*W)2&?nwk%!'
    'O6lQHOBfb6XBRvVMqnz`mlfx(K$oHYF>4@e33}wXyKY@YJh%Ca+qtRGB)pN9RI{fws4j2Y7dt2$;En{_K$`5c0Ot^iyOE^P71guG'
    '0epUd8TH1eJEGVi`yaT8RsKrl76H=VoGC#UW$_>;hIMci-=cUK%z^KN3V#7O{t!I`k8fu6XzWU#IFNiuP0F_p@aPv>;;sooYMb~P'
    '@Dy9;+L*0{Lnp}mj@f!E?ndGhc1FRRC>YHp;2`LIfd6QUQ)GO3Dl#Qf9s~bd^<+5m)sKzn!`2phlMzRQfI8K%15QcNZ;r&sU!h(J'
    'O>`{qptdvB8Y}On0p&&UtnvtihXnOgM`)<sDw-_4K9Myl+kA?J0dyZ+4d1ZX1e40F?BncMmmTK+fLiGKT$NLLYA`Gsi~Dr8{C8KX'
    'rnb=SLP!7MNs@^UvVsAxCg5||nj&z)*2O6+Wu|21w<1mgo+(Z9W~LJUxk8`kG?wb~(FX>H#_f0DFOav*!4E<383;1G)Prb!ZCGkH'
    '0C+=p-VS54-S0i4X8nN$;dyYrv)5>Ii>O^ud&4he55uO0EtUQ06^%2TOb!ed6Nblo-yUKB_pIim)z2MOHUrdlrDjFB_2<a|)CMAZ'
    'AfwMj9hGBfZS`B7EPc&zb!i2YRC-GbyDc#~oD_>^%Q67o!rA|+N7lp5bF2gE_dl)Kh5^cj=2RU8CKpteI+mxMU>57t&@01ga2YdV'
    'r%P*Ffr*1}-0uh)$Ktwfi8}e73{m+d$Uw2HzZ)Obs--SC*{oI?l*F_JQ>GyP3H_25X5BjhlQtlhbq-sMcc$F+*Gz!;iEEbAz@!;J'
    'Kg|?}LP?q81tSwELeRqYuYzbw7MOKGBGk+XdWh$U8)5wCPSVeA29WbHJe|e%ayDPwV-GFpfsMr`SoD%ET}RqZjN1E$Bq@WYA%qs1'
    'j4^GRlh~EFLPPCFpE{~U1px5bj)h!#P-Y`dsh~(DyPc3sgy13e9{Kf)avTWdMRVgJ^lOz}5X{q0mB9|!vL<jvdvTAZl)JNBXo^eO'
    'p=%^Cel~UsXhG7CA9_QYCI1%)4J#23Dzo|cPSA4;lRU-cMbpSU%kA&&jkQQhEN4N<*dgd~z0r4$EQh)bw{^$n|B1rc(sM~n&Mq_K'
    'C&N4(#w16l&kyTlH-q`TSi9Ru8;V|qC9tEo^jJHpRPwp<FfjS|`bEfvcn{%nBvQ>?vEqFHwXULjuQ8*(^2m1e`Xp}Mn5CQR-0L66'
    'y>X)p)DiyT#9JZ#=@qHHKW|>oq${|p%v}2y1}b2t%UMPMlXtHY)=uJtgDa&}?<XQH2-yA5R2C)}x~ek+M!6`??Qj?D=#dF$x$fA}'
    'bWMi#bW{=MNG@Ap1-?1Ymw^4p-8h0UtAxrmjv_Bv`=9F#EkTgd+RecO2?M9NO};2qdT0Ea?U}pWj$>d#T<6+>yCy3p+Oe~YkKshB'
    '@vHvv*vIAT@)k6JsR{S}tqa@3j>&omMrSeK&4=4y36P-0K9gKxo8L?4S3?;Hu|z;wYUd`sXOCU`&)aqu-%F1Waamk}Q$P$QXyMVN'
    'jY%zm+AI*r9K4XPOieJ$EFC4!d-kS<U<cBDooD!k;jSxL+UkA%!nLS$DRhWCkY|J9tkkg^n`uCY;meWlr|`Jl1-TAgxsRCKGG?B}'
    '+uCP1^b2l5AXdz593#q<NK}cc4yvy+#1O!j;AAsEV_%j(nB9l3E%``3^Jx_1!h$z+%`HmFaNy)O*M`-B8i+6n6oIUDC;P912gT4E'
    ';?NqAMaACd$Nc1LWgT=gK$S17W=hv8(Y_#ZTI1s;d7C}NspXPc=VyDDa90yoaKqJ{U;+=E=^Hbs7X|1WK}2`gha{<^xmC|*!g&Jt'
    'u2p-M5*~_Gcew~@{h8Ax+~9YIOgX{prNZf(wTaQG5s0PRWXv}b_s^_rPRBfIvIR}Gjdj_aDe?b#&fF6D%<`oG*4kI>#R8pY>kd%;'
    '|Croj57h7AEOH$?2bvg&$YiL$J!aM$8kY&{g5PuEqzHsH2V}BA0`LLRhh6+sJs|al&b2DE1BIqsVvVp3Lc{b82GsmUAtU~+J*2kZ'
    '%2F#Nl-BN&57xe8XkL7ZueyYAc(?B6s`RO86f9SQt#m`Ew;Hejym^9N`1v+bRcU9Qu7z3S=iIA*Lc<zqog>D6Sd<L9WYzca3+#KD'
    '{m*~XZ_SbFl?2Z63OlJCIfPk8VnY_o;&nEymdz!VZgR1etA_bg!+~YwdO*lxY((jjn_xUDkNG+Cd#_DNyg#JJmyu*m0d+2k%w4^@'
    ')G%p7AzE3v?RN~=zOnctxCZ%r(GuM@glHT}Iv|JN*9woL8K~wTr3O&|ke5Um1rKywY&Roy(<mnlS!5SJ+$knuf_`JuGq{*i2Dyl@'
    'vpm+YeU%t&R9JD?Ksk4~!+3#9#kc9`J2-ozqrwi~8Q{DL(6*A5C^3ovZ_}AC5rvV>mG`rOyf;|}8C{;ieIqoIUK?zeqa*#F%dI(<'
    '${k3EI{wUQuY}nl2n6S-wFC6uO2B`;k2fDeCS92l*drB5*8o68S2Yey^`;o>HJv3xI9NaIkya_|D{y|{?P+ys?ZsrvPc3<CzR0W='
    'rCZTFqgc~v^SY|5g*o^)8HY$1z#|U7kE;=n+i(#(<?2pxgpIx%9c`7d#@@Y53spV>u%Ol9v-(W0`NoKe$=$6h$eJIBKmT#RSws|%'
    '9?@>cgJ<gDX2pv?8b%=R6K{8PyulfU4t$CVYC10uQ7sFP97#4wR*&vsQC~`-CgUF2N(tW!`m#7dXt?f0=u(#Fi^H&v+W6UPg^R+B'
    '68F_#@Ajr^GB^%Z!3^o8i!`17VQ~A_-BanbbqqRF5MFaIiCYb>={)JqY>|{n|1n)1`IkJzY3=X@4Ib(Zl#f4lVlaZx@L=d*^YPR3'
    'XZ?t`Wp8xKm$SpxQ6dJDwuB#EblQX-@NKUMNl|!K2+{&~Z{rAY{A%v!8AljOjEXLrstCE*irrvuVs}_f7OegX{gR3?nfNswLYh)a'
    't7ISc4jgd(^lhH;_tS7_E2vIu^urJ##lqhC3MpC_`=G^iqcp+)J&^q`Jia1x0h5%rb!?$kS+#g}WhcET>J-P1pcd@%kqz!eU;yO8'
    '+-ov|(f)K1eZDJfi??%HTRpOoc&Hq_7DIu-iJb{}TG&yjBrjmdLvWk&CRc)UH*5t4Zb(E3o%ueuCpD$_m=Rdd;PS4pr&7`vY}_HF'
    '(TKkvJKqkJywAyaPM({`s0a)lT}zfn;97>4S-ry;1wUl%!(fbh)4*><Q^dwhoqXIg(z_e|{eNA9W}u2Vf@rdU)S|G>P}snAm76rg'
    'JvAQVP5Gf|VW79#oBG8YUxnOv^T3s)4x?Y#zy2h~R(wu+Fs>>b#m|TSbW(Pb&nsa@I-ceQmUR0+F^Zhn=~$DDY5dhR3er|cR0`98'
    'ToUMi@0--kCPQ>^v4oQTP4uPji3?;Qd8H?1Gya>96@4VEUT%9gsfO)!e{!qqG&3ImPGPYKsbWI}7$7basKwShxdh|?8Kq#hCW_<j'
    '_zsyQk63X`Z1b=y%CQ0EJ5(#kS`H|dN7UPSqx@I}O3)kV@tFgz%KbB1J9VB{eYcc&ZIGHJB*&g~fr0N3G5hWTcI?dV9qLZ2h0ZKq'
    'flq2DVHe)+DCKC=72UEP)i|@AY8wfwxcjH?L`M7_i`JLCygma>)WzXzo9GW+RV77V@V~?3c_1XAznjwyJIly47jwUYe{9>1Z^qM2'
    '9=<Z{g;bD66W!7)RP3~P8C&v2HR-+eJ@H-0WS{eAWJ}eL?%Fz}DC}B<RVFw5epJ0n<WIJ5BN!`5?C|L<)}GE`YMNqkO#WI$vqH6B'
    'THnXA5?1s(Srhf<ds${>)&rd*x);&j`C%-R>eC3L9d@kNEh^GYEIL1<3J%LSz|Z&g5W6SG#z-KE#buKm(xB9I>RB$nN>N1FS&1j}'
    'ae7ow85tr{yKIcOQ7&o#uSswwrGri&R8fZBe1GFkk63cXNDOm_i+QaEC4#l$#%OB1O@|$(%H^UDCyYERZIQV2)OaY>)M9-})Ot*#'
    'IUFeOikNN3ENu%eO70xJx&tb1*wqe0I`}Ls=16*Brn<4tq&QGabg0^%JF;(HZ-f6Qs^xuo!mp{EOP(3K379YC&kP5>-L$>~A30~a'
    'u!dAIqD%xzmP}}j^-rjnd8~lPwnJuqAt?S7Ov&$1tSsgVSyCWSAMM?Q;K$ilp4T-3uT5p6AQJbk9atpTa9048mx(@Bm%S)=pIXwb'
    '@V0SwV}1fIXsjW;cC2F`x22{Y!F8A5-PqeJL6g)&?;m@Lra+8<G(JRa<xQPb-E2*ZWBEmP`gQ@}k^BsL1y7;Pq{xxJNWf6m$(&S}'
    '3l^QO8r6pRB!44+D79;fp+&9INqF4aixqX#t<$X&AQTR}Dy{b1?0963^`qh3mg9?;B!?TbqRXr{wU%WYF8G4T`ks<HEt{&1%8s{x'
    'uD7cd5P(OJAPO(2^e@4!g@`$8&;L~Sj@4Gt9!nqyP4~oGgyiJ5!<9Q%tt#Bjh+r~C%*=snr53Y_lv@Im)3GgBpFVsQRa5H#U2VU1'
    '9^&^H@9Q2#$*2-)!u6fyg7L9&<^4E%61*OI#2}w55`?KOSZTQ2BJ5L0`@|AcsgfsufG88|-5Zv%Z%qz6ua_Bnn>KE9@0{iUay!`&'
    '$z58?ZMofZ-c=4&zIS`<DIXKasO;CKH@Edw3wQVXgbDk*oqVdoDf)N``ZxwD8gtqVXfTqf%sSnwOX7SrpLW#5gzT_ak?QE&T4Y?c'
    'x^4l*ho&0mZsr5NzKS~4-G)G!zY=~_KSn#W)1mqw?U;q4Ea-1Ro}bdJ5`5J4&5pKcv*SKN67F8d(k6$+E(6rGcNE%L;D=DSk$5pb'
    'vv55!S@2p5>=ORa9f>@5l|(V13u1Gmy7v#iWS=>vh1FNJ)?03>w-=u@>VS<q)=vF7Hxmhe6=^qZ-N)X1?GEfVP673hs5n~zS>YEz'
    '(6yGzKB4s8MUQGX?nYnUW`Ved!9FDHlrwD^o{B)aUs|!hgd|hxn}b7oZt{-4Or1HDpl!hb=YG~8H*A(ay59IShr<>cTZEM{TLj<L'
    'di-FAGHDkmpoK;h7jajdEW2jV)oc-jEKAw&Eq_4KxR)UCfb*~unYGa0LU1D__fR1+R<d$PUIwz!%oi+ZJzb_!s2>pgyD+Yf-sC(&'
    'ZdBwZ_fI~K#`Il|v)u>thag0_tjm4ialEXz#6SqpOM)zxP}%;lI##92Z*xbJ1nTT_p_&^K7>00m&^}k=JyjjnaA&h~iCNwC#Tz{H'
    'sWueX*|%5m8x+mvZwc1?QQULr(`kiLl~k98+B6fnK9lFTHynS#H2S~mReD{hF{iH8QjU{weDxM^xT_Uv6>^WH(Cl4<l4GIJBlo^!'
    'gwDoi672jd@?QxJ20u4n0Oz&9U)k0kwij7*L*Y0Hh&q{0_n5?mpjHq`WO;RK=}BC@Qj}`knfNj6QW7dIFq<e~L7ye0E6|4Cf?ytq'
    '22eYLrIGdpb@#<9`Bb9F;BIUUXb{FqNIoPkXi{=Hp<xc_cSob0D~Do>9K?>3)kuW^@5W^22nTG`sXM<{mI#zw7WHgUN1m2;Hm7ff'
    '!??2%+}p8Qh}F6;L8I#&zVRD}Jq_I)cd4l&=Fshxhjrr`%Z{&l0Hwbn8m$7to;pz)>l_<|YZ7Ocz%0#j2Zi2z&b@cfei$kAn~nX}'
    'ic?&>2@c8=Zp0>Wvuc`LUwlsw-5x(dDRqM4ImDJ_4I-tl(*Gl}o=Z()))4KB$JokY98p)_p-tEU8<`RuI|%{$Jk<O$1IsAt$Ah5o'
    '&hP55Y2BR*zu!(JOum=hyRn>xEP3@NuhJw)h>A$KKMz(!IzB0P+9X%RUEYi45(EyG{}wSMhh9yzw>a=oAJb`Zuhvgj08cpx2FVKZ'
    'INH_vn;7Z+2~&Cj|7djQVhIvTnpr(uBUggJ@u_9=Ank>KtV5<YypC`@KDFh>Goc=*GR|>tu;nnOjfy-6wx%^+;z^?jrnm2qisaK+'
    'DSfgtQwqB^yhro|f@TuS_of==1MyE*69icgFhOdI_2ONs(nsS5Q2)ySL2<UNR+$cd1h-(%3S*9AM~l}|$D(J#Z$r=y`+!b_U?SJl'
    '8(+hI>jjCO)y-@E+;PhZpFQxq_pXa3h6N9<v4B%-%-<=|t=Qa)m;2?;WzKS6wI&;ZCWShg8r>A=_q(0R!vOHS1X$P@iH%>Jn<&t!'
    'TC~arPd2J%YVo|?y2psp7~k)T;_&EM4O`>DW#4^V1p_CQ{Kj;+^{nVuvh<=A8T#mgDPQBEMQV256TX>2bJ~{z2=AMmQ)t<ygUptA'
    'QI+M=8b|h%WGBI-`I-f$L+IW6R9{3Gp-kHU)B{(1@L;5P-VI$1<MKFDpc(<KMc-DsG0jt9HI(ZC#BB5nGWkh;vsjpJNj2YbhiXTr'
    'TPFZ!&38LtI@76hg*gi&>J|0rml*H+o_pO2vh{^JS=ou^?n$Z0XG6a8C9d)mi%Tj(Th4{a2~SFlk{td4uv>7L#tNNVkyk16$JEXl'
    'cH4oU{@S*dZlfPGs3~lSsOAGo5AbcC8Ql%y!-~{-Dh-@uT<ShXj+}Y!D|QN#rX;g@oIf_26MV%9n~@gjSq(_PF_3n|#;OiKmvjsN'
    '-u`DZn8=Gds32o%UIJlp`CTjJO@SthNn-UjR3shVTp>of@BQmNJEVG77>60)4UZa=x&0QB0Q<%YR9rU}Uo=&ceWPANvx?J%uM_zY'
    'pw}&k7qzqac_4`^#k=;Dl&z7Q%&*)<IXD9z(`&|AVsw6`J`A?Ll0x5-SG62gkT}S)(w`I_OB`Tv+gYFBKc4%()YXg#OTVW;Ht_!~'
    'bS?afU8ReFrTRtYr$;bLRt(8+J}0Ylz`{gpkfLR1;&)!E_N06ezEqGfRJ8JYj!*g%2=(&OVoAJq%uFoB8$wB7(dRmrclGs9%gz1{'
    'vm^Jc?%Jd5isc*J{$db?{sdF;OA3*Mk?+X6A%q>jy4_H}4vJC|P|RO@O7I=+pd`Bc>G*!EB=pMo-W18e5+=qBn<iOS9!=`{Ge1Hd'
    'dvrIIZ=G9ni!A|W`r<YuXhfn^*6EvQgpA}0{bT)oU#jCnygVJ_O-DmOe$oZhOr%x(u>6-D%vdMv^2~+r)?GG=ZpunE+SwgC&wAqJ'
    '+bgvxniXwia);T1uzA8d?V@ssgKOif{re=|SEGD7+hc`2U@;^YPA4LC#dtJ^ww{&EQBI#As*>uMF49&0>hOPZi3R%g9(o!f>r3~L'
    '(bJYfi2MIDegHvw5|I&LJ)(vfgZ|!>uSqhN9M?ZjWYF`=2Mn`crFa{X5^+>XM2xn8BdMdmH&;@}V_}^z3+{bJykFU&_Ks^~0*m-N'
    '2|$3im1e#Oh_#Ce0JJkm`NAU$7E!RMd!d4k-t0Ns{)DdHrX$H%>aO6#iyx+%CHT`?|Cf3$tFgt#Ld>7cHIhE~=H<{ZSYuUNb@Sb@'
    'z^GJuJh-z;L!;gOBhY>Q@HXMj6p1xSm|YkOi{X!|TqUZ~Tuxgupv@^x_O=<p>`Jh6RA?q2DlB)p_c#A>uD&_ctsA`cOF4CqOAW13'
    'I9;pW8e1gP0?()y4nLatAFm62%fY4T>+ffh7TV<7KZ5{f-!viYe)v+%u9538rg=&}p}LfeK3bq-CzJc^L7WhmUhZo)xLuAXhAGyG'
    '<hVz=Rd>@J=|q_l3ro~68%R<$$`RuIm|(j_&m?(gu^-Fzu6+gHNiT8hhEwq)uSU)dgpxZRGSVEM;Gy9UfY)9|1H=5x?(w1$$hOQw'
    'BLqrJ)eM2l%$^<z6PDvNC`q5t=;`k_RhCUT@Oo`q2gwF2Q6v@9SwmfA?UXgBN*TlLDa-og2;eyvDed>A=8ZEka#W*GMc#vkOFG@C'
    'Dk#8l4#Odlc71=vkx<?JhCf?t#PcYZ!NHNO)tE)PRGafB`K&Sm25E2ll7f`i<DwqT-fNpmC<_+5`34E#m7n`c`Htq<9VAw*tGv%a'
    '8)*=IQ=Uhb6418#U1RA~yET?4gbxDc>)${D>ns$I4a)DIS&Yo<d;HJdE#(H#)uHHcN1evXhqYuUD_3|`Setu^Am+2zyzW|g6*EzI'
    '28gWi4ZBWHhtF{2z<sh+wiD|+csBNIKRe4{Mss-0?;(NtmWg3~4~NMs7QS{S>2*Mq=)IW;Tc`vb=7#opE!UD!qkQSkL#F?k5U{E@'
    '|A!y-D8S_&W%pg%*IS3N)0X@MyOTP44Jrr5Ra{A*rYf%9j*9{+s62ZRI%lZn@6h8G_(q<#<RDKruZhJHd3pR-LjsI9(dp0W3;vBH'
    '?ai<I;aH{tENgwNb=;k%Y0UMnNs{isdB-DP9x#;n+O7i!ZTlKm@%ec3h<TWn!|GSGu@3F)xY1)cLSb}jd?LwTl0M%PaJ(5>QO|1('
    '>KbLsrP3NXRoxQd`jCaY^J#FosY6a5KImtE?izcfrUV{EF~@pbgLedudhfXWa?fOrCd8#s%<-!<TScBd+}W^U!2yJVa^6ReGCND1'
    '_eF@*Ahdk)UgOEK4U?OcbD~(<6O4nIM%`{Zg;j0Tkt)b<5dP%so|}x5zp$8mnaq|ydL1}`rCR%(@ScBi?0+y;b)>f_6Gz5gmTSz|'
    ';Q{vJu@fS@FOSeU1g4x)J@a?W6D4S05w~tuU|QIN<4})28aLT7d$VZAQP*EDej8h7#O=teN*#Gge?#-IBAO4EB3au;W}2`?3s&b5'
    '$`h<`u2(MI&EC!Z_aSKkCy2NAqLxCZf-yi7fl6G8GRS6?{hhrks<9WM5s}m+FB}s5g@bI^*%b))a`SB<056lLeI?sD1Ir5@e*kRf'
    '7zGC$?l})?+yBubH$eP+gL9s^lJU^UmyIM1;ExUrOqMCByN1$f6lLXt;egmj4z>Yn{ix>gX;8zvzA6o(COx2GJOXeNV8)uYU%D@%'
    'm?U%lX$}7LS`ML@*6{+_%B0HUFFn^gH*|T3F>P1Q++ba8)1@H$O8DrvakD~vIJpWXrOXC^ZPO?V+(eU5rabkZT6&;X_;ZIZ;qy{h'
    '0qob3{yIx{QF6F9nn5}KxIlmp&314j^`@eTB4wpX;2zToRGov6d=T;ra?R9>K!Ayk4}RJJ))hOlK_x6WNo2`jBb_D?+z)7_gzKtX'
    'CP;<aL<=fo7Ky6tV%+MT|GK{7;=Jo3D29<#S}*9AyJomNWj@a=d)AOTt+d2z*HU8(mUCT}8ioxGd+NJtesjgdhn(R30f{+tSeo;S'
    'Jt(7*?NuW_=t5m%MNy{xaQvmF#90>QW@9jfdP{3~PF2ymY)3X>Tj-1oXG;c`v|oKNPdV_6;owitCJ(9etJEkk?a&C}(&cXtW5kyv'
    '-29Tq;6<;ga&<HZbnFc72{~XYL*{BwI2}Ibp^bloaZIa^Xq>LLBzBrl5HINx1RtU$#g~xo5C5Tp#O@+&-~}9o`{9VBKHNT_$UzxB'
    'n|n|96RH%(!8cF2YO6Nn4|N3>*x_7z>Ej7)>YIdM9&!J#Q+HMP{<y~-Ntq>qrJGtu*nS_6wKx1ii(C>1=3q`Ti;G~zOO}hua584$'
    '3U>SXX~2pXN@^yS0};91bX9xd*mlVQcjFy6dnCl_qJuPQ@7T;>^ybXe<i1L{$Xlg<?jY}IDD}+i<S)?R&(4z>qy#h=)qd!;1yxK_'
    'm^bDSmP?QV0TEYcQgPpuKWKhTxP3WGR=r3TH+Torh!l8V0V3jKB<7IzgbZ!=Xrtco7Q;sAdx*{M5PckyJ_kza04H40Hw;)2R=g>8'
    'HE<<a&=0Jpgr(FhK5;!EZISawDL1ewx&Prbs@j7E3;1or*U!(SsA~b`U@a4xm?$Uc8|^98A5E2*dR7DP_sV~IJ*K3oU;pO8&ee6w'
    'u73tSFd!IVy3S1|>|lg#PYD8(vEA!&gGnozhpz8#Bx#+fq1n$BD0L4#6YI90=V__#BhdB;Ak`oYy9YZ7b|OOV71ev8T3jv!`V&Un'
    'fGRDL$4iqKZdtPkz@Fcu=`3S^kx({k%Pvv<o`kPqpNPvs8vC-r254HMLuP9%4Df+buxlm5Rkym)X)9~8Ef0iX);0)&eV*511Ebf{'
    'k1a*H)vmpWufecu%2q=?dAm;u%g%h+yadeQM6Va9ohlsF*^RxsSY<>V%u-?}zB;FUHNjprTTS&ZwwHqGU?h4<k1Zd!Pj)NpY2A!O'
    'Ajnr(0*9FFIK=aF>0_loDH9FuIa&{k0gnBJdIUb9a}em5@cytPD2WZ^96Cox#%T9zIA~ugN+UV)!*7<{;B4B4#)|r<fIVDCesZ)X'
    '4>SLmNh;{zYZz=Pl_+iNfzJxv?-56g-u+d$3fI0#sqi0#<{srS;V%Fuq7?hv2~8I$jvys?i5k@i^mXfWk~$Q{MpH~dRE8thyrdH?'
    'a~5C+%ARjJO5twI6Hu+p_`fa^#XjeJ?Lf}v7;r{Oo)6J<GAs}LB+Me{vCWfCAw!E6887M%7AD3QUr1ZlN1d(_?R&*t^p&iC0Wki@'
    '9%fSJ#TaKlZl7&*0(=Fs6E2v$zc7~ittL4uYLK|M-dAKlGKMU*lLG#>FdYc}H{Fp0qh=9vQI4e}9s2XM-WLPFC#H+N{n*kPAE#Q~'
    '4|xQ62hXNqdPR)mlT*m2nj9jK$+Yt?wn8_g9{sui3x5W)6lJVPs*}68SyrrkHPamYhpDdO+nCsIsU1%jRw*oZv876X{=0NK%+lMx'
    'v+`k39~qW8aX5l{q9laq5H>ae(dmqmWdGpnzxZ$<RRBo1NCEi2XbmkVle$b2o${Em7}``$%2;legLCE7bARHj3+n@21<#Ju-z08l'
    ';k{p+Noq?y(e`c>^}L91)=V>q%|49JjEE@0Zh2bE!(Cg!#p?$!85H?QZ~CM2y<cx#8eA2(`5DG>w+j#`T5$%ls9MwNQD##r(@`H`'
    'JbF<vFLoK_+VvphC`T<Tax|==ysWU*R@|IcrD#9W64;>@gE>>477)9MN?~QZVqEomXtx&$=ogD=x@jBRRc&iwjc0io(ou;*M$<P}'
    'vjRmu2eCfA%8`^^XZdB5qjSQSty{uQk1)?uRiu4ZqU@JRw5Q}5G|!%b6}XzI)9&;>&_^IEj^7z7_9A+8<-|J_-Xa_szb`|OQL9$;'
    '^^vIQn69``Pf#I=gQbY$));1<9FA&-Wy^)4*NHmU$~dtw1lvbAsP#Mkcfny)n@~mdWCJ7$pZfgb$8z>SeFC6;39K!{E1cj&aCB8Y'
    'Nt@P9tr!Ma(v9pnt)pmO>cw4;6uu%pf~XQ!?k;adA`@$ik{ZzsPXH;jpwKle@aIa%a92sAs8{I+DN<6cS!*^iGzAC`)3{kbYnIkt'
    '+a`bsV_hH=kHO<;?FUUwWJJxm^upgT%vp%ab}L@HeTZO*Nyh}ie_lFnPo}53Mfu>Ai7d=v@~i0X&VFzoecd0T_ab-RIL#-b`Zl`3'
    'sflx{VhPhAd$tI8&wLuebZ@;1Gr%{F#29tZ7&cJSgdf`ObULlp9H*=RBoCtKC}5htM^<er_Yt&(o!uq*$3L7`>y<!==7ZgAUxdHe'
    'U_tT=Q&a0%eOb$@92STJ-b+P5tT0w~L*R{~kLxD<0&IhGv;_pkl~FTnAMIw{+SK$^wBW`f>C)ovh)s78RDv!tAa75T_j+5czes2$'
    'J7uI6P<J?(|B;UruUqc-rlJw<D5m%@@5x`)-t)wrt;-8cm%P0{+(wmWmT2C~HiGni`gcjI25>$5&)_ShaJ@$X2iycp_(S`U5Wdjp'
    '$)N$~qdZET)x?2C?;=NHYbyS46EeVKyrac1w^Hs#pkfwgK@vFqa%!94651IPpts|ilF^_R-@+&`hc~)oO}Wt}UCTEmK6$^)9v#|T'
    '8)b>TPOn0w*Ep)%kp8VCprKlSiJjuc1FP{Tbum!wC>kpvCfv{pK<bm1()^mih>Gy@R+;IZh(8KFsy|bP!;YwBn>F|a!5iPuw`X9<'
    'qK2jAW(SgbLDC}7B9~wQrF_9Uv<7=vcLbAX)wR<e703Z^VhcRV2baq81;FaYU0s(Gni`VszBKqrUp!*qbEq_KBA5bfU!qI?nrjKS'
    'BO+!iUYVFL^(JcsJrw%vK2w<G-psb@(0z|X&GYwIfn``wUpS8%Yg5c`QZ?}h6**5bl9~ZVdU!n%1Jk|@Au<|L(fRqNwRcWUZ=p2O'
    '2^~yB)N&P9EQN2QIxKN5Tci7|Ei*D5=gG$?j^n|=84M6++D9$agbZ%}!oUfCVo<Q*9H@DhPfydviseRMkK9i&BD6opkXBHz?=!|q'
    'V3v?ehX<L-J5g7?3&319eEb}GIJ;_11XUOQP#NpMs|vn&-Z6gcRK97@AvjTo?rdg^F_Ka?I>0>hDP;Z%7G-Ao{<PHO=%A{(Erryn'
    'U}-74JM9KvWhGj`xE>kEBwfp)Fy=#s9QCEivw@rql(H_##Ra8L1Zno6r;nHNnC?g{R}9Ai1kd+1J`(#>U=W(1df%Rrz@CnQ%T9)A'
    '2b^u}i8v$KUHmXD6k`fNdOP*&+v_{f_eUgwxp^N(r<+kq7V-0*N>fl|5~eY14i)YnV{I3q$}mah2^b!LSEPvNoVgEq<U4@Y`%V7f'
    'S&;;_>+2ej0F+el@YNqj=pn<vY^$=UIw&>OUB%-)ky>Xg&idz6!J2icFxwo)UbWZ;w<+08dac7f>xTHQ4WW*WZp#;w3<@lSq^98s'
    'f;919E2Q){3ALP4t-`0Zj9Pbin%%g3ob-_28S>+04T{4mVf0(xS|L9z=O(vV|2={pXN>c*p1~R@OQhhnq@R#Z0ga^<mRZ4QgIrHV'
    'DfqIp-Y$CW8DlBNVo%4T$~v7mEBXMttjRK2Wepa9mN-JO)kxMtH*n<ENWC4ta9{MoA^t?SK|$Tx9H))#MPQ|sl1PzHQH8Fw1zjh;'
    '4haaraF!}UPP*M=&-<B-SUOe|Xnu2^oX?bNpoP7|6~{Q$cYF0#F+Y<%`hjSW`<}T@^f^yM$;~*^hx|&DG^ZiJ%PyCAkP1rw(m)MM'
    't~AaALlVXFRvNA*lyZE(SoTru_nEqSHKsc*FboGw>-FZ?RI<0=WQR@(Hul05IxU9OT2s2T=OcxH&>T}7wpu;CEr7~BA<eUO3yRfQ'
    'XF*ftf**Y%2B!TTqDW^u<Mr0YR7@$I+{Y6A2$+mLGI7P2r##v3c-X*FNha~I0U(VHztqzDYoS^-m#_Hq?xI~kxqKhVld}ISh-nU~'
    'lo|(!onYll6TH!C7!L5yG1rV*a+u<>UX7lUUR)x({in^+-<-)*Cm2n@83C^MBm30X#z-daYffNVJV>*9vUl7sFlrPEP^G$L`+#oB'
    '68CJ!r~)rU>8b}o<o?s3^X%+u=fNM&(Cx1U$MS|GiehVq@Y{9QNsx3kcy-@H^hCfiW+m#|0`P$x^wItRr#+}b(!KmY5JTTuce59E'
    'TlM~9Nz+LquMJDGr17cZEf^^IP(Q4eAD^s=E~QQC2ADcgzEwm1dVlN;muRv)2YvCrp^Iwr@b(iXj+=u)a7GbkLwnzu-vz=pQQfBm'
    'FEqRv8~+ANC=J@3I^7=bl5B5}$3&LK3Y0e(Ktqe&#j1alRua_}v7V;pZ0hPMM%goj?i=%<>|8WYDJcC*Y`76HGb74Kx8sdbq<@wf'
    'YKzSK*+jghSQK-;(N&xqZ=HmI)L1d_m$#R^4$rJ3FxX8}V26!BnH|!KJ7-3KVwY#A`2=d8Fdr*lPe*2C;u8xK2=J{!_e90rM48_v'
    'bE-G+|4E@03(I~%ytS8b|HU=j-=TK&J2w$ZOr3z+iui1y{+<sj?#qB!j~6T@_b&rOkg-|8j3Dh5G^W`NJiTFd=P3WHWSD)YF61j4'
    'TRnbOlOBE7YR4$iDY8~|!h*YX&l!!Dr=be^d(}49tdX602d3@OsQd=J?$!u^#%HT!h=Q?CPU%Rc*S@=LWl%szzC##@UzJp4lHCr~'
    '&O6PeeX{V3CQB%do6vFXN_rE}A&yJ$g$OzdUT!Uj)rfd7FOu>5yjkasduWJLlMX;*AUZu|M142?w*G4Y55q>jo)D4`F>mh(CzM#C'
    'ap^8Mh4*Jee}CgxM<3wZqp34bB&K|F*uyNd8>p}Z8wZRX+dw~CJ4h7wd3G+uAun;dG--ul;W*i;q6zf0)JsJ`bae)GyAduGyFV;f'
    'r>j{5Kbd6HPW1bHrhh6wBMTlwJLviaFSsJ{t*7=mHK22<vHWP=(L8-H7!Y&3xQMGNZ8d$jx$2xt9MwBI1kfGvy6Nz?#?Gne((K(o'
    'eKRfFk)S~nb|^3CE7jzBo5@l<PA8JS>_C+$Jt;knCF&d3hkYwY1=jt5P7f46JNT~_&)Sx)Fu#Mxb8l_zPVHtCXTQ50cH}Yz<D-JS'
    '-{&@Vm>JwZmsj79QV?r3xb#iR?B-^<dlqhco%|%0_}Q*g?UTkP85|ekZeB>0!n>!Y0U3;>s``OriY!5)!z2Q|r2$1AsbLijfo*si'
    '0e7^{EUPuH(ojJKmAHB0%iW|GZH^RB@^{{>k+?%i-(bH4WhovBAN!=2J4__@?{M^4dH27s$yCW!@i@8#wzJY0mE8tn+%^C?yexUa'
    'kSzx#;sX-shFhQ0PZ3apGnPG<c}Mimf!CT`#{gb3f}GDM$mJCVgKp>V9mZT%fYE;)t`BYYYTRM2t0w(XumSc~MPCRUE`r~t=9%k%'
    'Nos&$?*a~%fl<3OOB7NbR4%1RW!jXnQooB>0p}!#YFjxz(_x}?yhn;qRJm&7qC$9s6?65!WyDQ7+JZ1z;-ojmd+ah3KFmU6y2Oy*'
    'SIO?@vR0Q<25mC9yy^7P>IWmMtr6|0oOV6IKR4oPWeP4qH+`w=6Gd5`N>53LWq`^~btZWImvTq8rN1F^lVXmMX9ul5&DgTY@KWtP'
    't751mCZ|VpvfUJ$vX>eHv2MF?QuGViPWGn8m0W|Nj5lgR+O|r{Q~z2%1~eX{25U;-Cn2VD-Alr%JI~-iZhYa5%WC94a6G96@4z`f'
    '{xF+$VAVhBw7Qm(J4&e|mB;?7nGqlL8t<jYtG`F)HiVT-w~Ks1oy1WuKK1ES<im)A+e*%#k>*`<as04A^-GjaBit-Dlg0X?kp7%Y'
    'H~|u*dD?-ie+|yWL|Q==Q8-z`+dK4;Lp&RY`{ul7`VYm0jN<RguZwjnn4aian{r%(2U~|78oN4$v3J4dyhJkBH8ZWAa1=nNWe+Ji'
    'T`6NGvYQ^BwN@|><JP22^gHUY%@FRJJy${1a*-pg?E9+W8qeSc88d#_{KRQ84khFL&%{MDYr@vX5d#6oS?UYUx?YhOh-PFT*hf=>'
    'c}#>H(_DL)6)(!4;}Q9NBXgv$#j`)i)weUE!dQR0zO%{Zr=U2su)Z<WVjL)<ejAhQ@nJ2w_>-7i@vZ)IDC!e(xY4aEZKQ%sltJLD'
    'ZsPSEMrpKwNCbQIn+F1*a0>|0;lw|v1H)u^l}VG8CKUAG#m7%r8Npet2A&IMxI(W=r88hbjBd`y(hkHm3Ez<4P&oZc6N;W>ug2?A'
    'AhRd+YEZt8fJzXm9fY&JuHzGveA4jo(a^M9T`=bL4<d0}(`Bv7S163rY;sDHqLpTx2%Sg4YW4qA%>scePJom-$-DFii^n71_OleS'
    'Ui=SM8DV+Md8u>WyDVo*ifHX%GrQ-*8ENJ(u`Go+fiS12cF_>&%+B}@e-*&?bZQ6dst@wdKV=%RIsPTiBVw@kTQ*we0Bi8ICB`jz'
    'LyUpF&V&&drG$6WiZWb9iz0fd{0A42^`9Bp1!VqWFkd5h6yP!L#XZfluZplIn2df`c}cFmSTVDHn8lwZHmE+9?4F}!gntBibFV?9'
    '>*k!`NILC0#NU&&nR@+J^|0}Eb2t$F-lQcZ$}Nfe4<SOMEdVwqWAEK;m+Yovr?l$vVQA_Qx+#WBNVsymE8YN<b&{l0^5`igG?z_<'
    'tp_m}*Y#bk+c^m4uG7n6BZP-gAqwa%qhrMof~3|-yQ+}H17YhPclJ4AuAYbM*hk-XJ<9{ZQ{mp;{2viy0CWa2h)UJ~T5`u%c7lox'
    '6rzVVU97ERTfux#mZx6M%Cso6PEXtmLo0h7sn-+G=`zMeChA05*TF;k7YFRcv?JBg5#MT1N5I_CAf<;R$zI_$@~VwVj%pQ`bge-5'
    'sS$#jQ+gWMpXG*XK(H<<`2w#kQ7Jsbu{xzG28lL7S~hvj%rBGy#N>ipLr8%vX>##m6GRj8tSwf1Gtd-^q_zw&{n}tW$m+<iiToW;'
    'VEA3-Z}ZuUl+NfKtK2?YBc#c1debh#WBStn$tPi{!*XG(|3cc|pOY!?vK&{N!`^i$qVymGvnGH|jL^rG^MeUWAxP`rQE3CdIboTc'
    'c~sLIH6Q0Tz<8CvF<OcOAL04cxA`{zOR|M*pGz9H=#ud%?r*qJtB`X3M^{$(0Rk*Qyq<(Fw7pms;)>w^!$r@wy)5#2kPKqh?HTge'
    'Zj;NDZSSV#MF{Ih42mLuiN6>UhQ7YS4%AZ16+k!M8^EfG0Y{SU+sCn2WdNquu%h10*~`+&_wbuxCmoQ-Sf~#eTGMxPjqnb5l`xZN'
    '92mpz%HUeZWs5l=`^M+gA}+0Sne|6Vc_ZiHBn)h6g8)Arlj>bOOtdJj6WK4c^rrg`TfQ<*AE2r|C|M==eQiY&bCk@}p=!Pg;umX<'
    'qgE&`PX=sk`GdNc6G0}7LTA~>Q~Guqqvo{gq=!VNlie}#l47r$j<ajoH6FTx+{xm4#6AE>xeB8sjW(bC%DB--^QfgMFZ3br$nh~g'
    'mj_^@&)>x)ZVQRXn340RrX}aDM7Y*9tkVL!ois8WZYj1#qCJp!43}BUMdLUWcbZ)!7X{n47j*1xxOtoQMK!iKUw_Iba~2fw4l~$5'
    '8U0>7t2ACCxD^iBUgGzZZp4y?;m;8t%A3r9LRQ8kcG1&JS2{h2YZL=+YSxvIzNg!krFyh5A2^t~Jun$XAnTdYm7nG44c0#UleA{Q'
    'n~llpPOm6SM^QYwTVEk>DTToXSJcRop{!rC!A@q`V!e)hZiZ9ya~h-j^9T&HiG5*$K~DL+Zj9W9GUjQiwD`wYeWSH712kIBAhfdW'
    '-MZFiuo1~$MreBi7j$7LPv6Xan$(Rl;a^>^?2)Fk#pQm;iEHTJ+-n)K5Id9M)Et3xQ|y@Z5R@l(fn9mK^otnJqh(_7;Kv{06R5v3'
    'lmklXkqE#Rz>Olv_xIu9ZK9#u_r%5v+9FmTfGPpRLkO>Y2PCiSs$<1}%D&FrZmMHb6e{l@X?17vwhaKte|XY@kAs`w92?hWFW$`5'
    'F{R-LOt;fNbdImXB?c@;>|d+18{L7H8_`~yc{je-r6;)zLaE2Khl!Yt=5`@4<$c>Kpf3FerE#2Tn2n71J?MeirlRS?MVrRhS%A_n'
    'VVDEfW5NdT7=eftJQuVHr+v^`x+&)R53V$?+6gKx=F2NFQ_PKf$1v6?1DYk_`mJeG%|rrG)_Rt_)mEMnfas_=M=Z+sNC*tAUwgV^'
    'Kt;KIdB7{6(4hitJ5KQ_*6{;!pSG~oqK1eHH36TS<{DohpNC;K1xLUrY&5vCnAFZbFLPN1Aqp353x)=BTMWNrCg52kh9h@1>}dL6'
    'a+BWDW+rr{w$=4an#!VcDa6f#9Llp`TXf0A9$b2^f>AgDWU`GbY}T{s6PVw{8ErVk>(`PazeYC30b{S90<8vl<)KW+_@mo?)}{H|'
    '@3-flSi-GGjm7heXLyCq53iLyENpuctXjqh4l4c(KW!7tmYrK7d+Uu1xxUuR3Ud$R9d3r(;i!+)u3=h4wgbXmLzs~cg8W%Ncj9}l'
    'K9<Lt8eX^KIZO6k_Q+)k!Qe@E8hbKJXTskEv=`uzf}~lydH=j3`umv-e{5Z^cx(`+Hf+(27_ffw`FMrkAs(-K{Bf+8BpJY^r|JRS'
    'lS<CFcn21~>NZ&((X==aZh&b|+1N<pgR7oyr@+}OJkEeNSx?x(yJrg#;kr0t!Bu{05s5j5+R-_{@L$zr{XovNkFTU85avEy@N2?J'
    'y9YUeG^#MbbKB^i#b%f80TfJ0ZiAcP<`KOEFBe<-@E+)|a7iDPKCe_z*bP7Y<Z=LbyHJNdigWM96&j$Lo;mZ8DdFwsztS?%b`*Sc'
    'Zf)g<UdwuBu{BOGM4nF$q7=&{aWjuNVi~0zH>e{9B9nJ~DrO4qxguszXw(aymH}n4=6Mt|MBkv>3)E|9bW~{<YG+g={Q6{|K?SDb'
    'Qwp7DW41$Gr;t5830ntAmt=l|yKpBtQQg?mBaX86wWWRj3PlkxSBNw@Q6%6)cNZ&ED(6=KEa%yruR#tq#D;>qHxv9B3!Zhe`e@xa'
    'a{IBBX|Ef#2>HCbO1~CpPQ*&XR~s|Qrs@f;C7Tf43aspsPIWK6|Ip`hH&YR=m5ez!FXN%o#w37yTC3EQvl2ZWmB0oB%K1(91sg!K'
    'th{Agn}<8;k{llF)<RR?_v%VJLo#oLQ*@4cR)M5>QveXN)tTqtB}?uSLibtBL!ccjoN%6vqdnOQvW#|K#1lL$IK_;+gyRK)*vA!%'
    'Yo8Pme+N(UN?DX=e(}NUmwrs01Q5p)1stEv?;Uzd7`96p$7$gaRv+&L6-ujE4#2b2B%bi(zpyg_w52k6;Pp9yc<845C(n>ASL<OQ'
    '!Z{xP_pY?|2=-p~$s$?D%MitA989S8Fzse$`>R9EAtFE)_S%4d=n(R!!dXfK)dAJ$5N!`BH*>v5;9^^cip3!V8f+~sE-EfhFS(t5'
    '2Pf7^>yI2QM>8Z!rBgdI(>$_VVf-dh@@ZqE4K6|w*eUMf4N!2IG{2GuG-GY;JhTywfqpRal{g=aB$c&Y2JdfCS$&Yhg(Q%~5&O4C'
    'GB}K@hxWtP*1ulPmh>N_zO0j4%kYg(*Cf{i&`!+P&+l90^1{$04>&wKd0DAcq@I`k`Qxv(jr-;ps#>a@+pvE4G;`krGUAXhw)P_I'
    'o%T^zN=o4dA|6^I1~6BAC7!aWW;Ib-&V{nPO7_TJ(mJ!gLNixC_q@pZ-(#v+{W=cKd!=FjIIHIk!x1ckJZ3)?TF_)u-l1b_Qq~x^'
    '0gvO+iXmSawFJ~V(%F2yqx42%O@2~xZznjSi=ujwF%T&_LhqZ=75?KJ-+Vwh;diu00-Mjn?c3|r+#X3qZ{AK_)Ka`^dy=EK(%Yi2'
    '%k@XdLQ*9dV6>IMfl9u*zD!-0g4cVxawtP-vm7yxA+$RLQ$o%AFyxE8c*9;vXfbO9VX$#P#bh6q**6-;{VuSRing2QJfB<(sy*>O'
    ';OS;lYb(|Hd_3QB&)u8impPBnkj7c5-1v~KVTX&%Vxw>X%Yv1S^olNf9W0W%&Ut{bN~$c06VwYg3u)khK3n`-<H_poCC0NbvVMyq'
    '<||B4=Ad|m>F6t}{+W+LLx1U%epp*DL($XCL>-gb#EDWAjZU~;0lU!JBWIi7(*a@>4oSpv{y0*$fAV|TBi^I4wej`tqfRPl7e$lz'
    '#j%If<m>RinBFPY+$H~NL=>_%G)3y)gWVIr(pw4McOU}W8;SePoR--bVfeTu*<wLkCDc4?P0zC_w|{FIvFYq!^yTu_U1Kv@xNu{q'
    '?VOjpy_IoB#qQtgOlL_rt-4JJb)ykspZ^4u#{hwAxTw<HN;HTp-wr9Iq1dosQ-!ENwrM+@mt%7exQa<ot$NQ`wVzNZssw4ah(8g8'
    'r&9KWf4Vy~D_);>OIf$w4e}3tw_0;`5W(<$ysk{x<$Mr58_?BnjTeJq%&9BmoP)vACVFo_d%2EY^+z1Z=moi3x}5obv-rh)Y2;hQ'
    'h-EEg9G*%J6-QfpNK}L00Gv#tr_m|Njy_Fo8qXX!Sn#<7SZr;(JyT3O8r)iuhZlrgw7SHu(4Q!%WoIoKXUB4bB>$#bxIXq|_$dr8'
    '@<Z%dyn7nh0sUCrjq~K*XB5kJub82~PmBVBOI|U5IdiV+0o(^gN>?K4#oiqr<o<XN+wbkzc2K6Ngpj`Z0PkqSz2ygM`^Fg0D9dIO'
    '2xodbmNM`&>aouo*LBbt(|J-ye8F0{OW(`=9YGj|gO(P`Bg4O5Iby2cb9|~`cCP$v#&MJ<XXxS@CC>Za%_s(u{9c*h`t63i`D*J5'
    'GKXe3@>*Jape>FGr%knyuoZ~)Iggt$Ly681v?#S@aTc4oqC_7oXyt}UzMFe0zS>g;R04=vK6^s0_zWR7^pzzprqNroS|;-Y)p^-I'
    'AGxRn6tc0xYZQTm5q|u;1RZ?a7RS7_X&ZZFYpKY>(HKQY96VUIuuK4y;TrX!hm|6$Cl6{uNtLSk`z2}Oa5F~`#7czHXE=n)hfEi0'
    'r0nJum@jiUP#fppIT)$Vs<rFJms&PY<kSdZBBYQsE2fXw-pNL}_gUmh-Asf)%$Gm&DGS{iRs@2lUgkcnUg^vj^G<gM<*XCxDEDJ>'
    'i*B(tSUPh_IP0GBZTa$$h3pWt(_t+Qd$eX~3tx63C)Vfoip=A`8u{1TbV>EHC%&@f3z?!=YXw^T?W$i8q}I#dbrITH{n4xw$$Q@H'
    '+5>^C9?*GY%XX<KG68X1Aqm*7vJnu6R69mCy^B$W1Rt88JSIUJDKMwsu`jF&UmheP-@ruk*g-Kdlj;Gr!aXa49K5q=|Hi><e0w}F'
    'I3iCQpkpfmWJVekf{cCD^|v+d(vNY<@AEtUN)R^i&6REx+&|dCbi99GwT*G(6(_Nl$E;Vc{bn^Exi4()oM~97ox{`AS!oy5!pwA|'
    'A#1O%vcK-<L708~4hp#;C4t1BWYy%OC0BG|G1V)Pvx9>j3Q(;eT$;eUw=xe`th43(dVX^JeJmyR=KO5GN%5kWA*Ko_RM`6XttFcH'
    '*1;oh|9zX}TXa3JVkPHZ;^5|br}W?E$nRFY8EQJr{nr1g`P^Xnivr@2Obb3a%=Y+c|7A4LF-}#QCqxJyM9<}|5gF&`Yqf=dL&ZJr'
    'vxB{|1^yPrXb4dvRJbhYc_~Q++TRhV*KV%qi8bp0ri<EKF->W=^MSTxfx4*!@gS>~jYW45@|@h>UbKeD)_^;-TRH#LcM9p|Imk(?'
    'IepLMOi4x7>r4_Q4+9MCUNG;0TYGg=Q~a}gT%tFaM_r<GH5==G{_C`obR2?|%xQ)w9RFdeitxoF)bYWar*^%p5?Wk6(hZLW%VnJZ'
    'GNoLky-kLOgHmMNgwYsd0!0S<2ag=a6!>t8556amva_SgLD}l5cXM8iw1HBZUjkSfNMgBjOo4946+_#*m11^7DPmi=TLPw?Ic9!2'
    '>@SLlhvzyEPE4|e+~L6nAtQu^ZkWV)9qAo&-Q&0VA@}9JAqOxqznZ5U9kTr73sL;sc@1;8EQJTmIHm<YE<>{pmmIB5bg6udnoumd'
    '&OV>#Ro2DGZq{1bgrZz(d#=#&QyT<?4a*$+iVkAkm2%-$j)tCo1;={Ga%$}^ZuS-93x3slp?ZW0wC_#|QB>2EJgu7NBCj24@9{VX'
    'GsxBBr%wH-C!NRKFcBpO!KkDT8-VjLsWYQF<%;Nm*bW(2pcRIGQSyKY4Qu{6c+_|!sb!cC=_YQ|r2@;?X5*zKJ;JCvboG#E-muMy'
    't2k0Cl6rmDq}8{x@H6jc_;5>iRRzV$prIXGNKRscsrarcpQf`k`KA{Xs$L!w?QL`7LE{rNIFN9qwu6n_Gtc+TT0zpvYQHqdhSax%'
    '`_({!L#jZN8AAb0m^A?p00r-Z>C(d8DwMc1wyFShBnq7Bbdk*F1@iEQsz7dCv1#|JuV;RTwjvBvZR1im@;t}cx%Y-mq6hJTviC+k'
    'yfH~1I_FMFsmv;d&cVe`k+0on9Qmur0j`W$P6y?`V;xGG3vi3!s)OZ*(=Dc?3huTRVZJ`e7lD>Dd^^(+$U3dC*d)ecsmZnN1_QMk'
    'oc^;USaT*Na)RlGsi%zCOMxs~hT`&reVxD^Ob_ma$wJeEv`v-uahmU=P8w_K9>V7-_Fps$C!te%pi*CheN-zB8qc|3p55|O`lMek'
    'd6#$=bWv2kdyQ*-a|j{iV57k3D&IjRKQYN}&K7H3A!hfvN~3eo0Lv|AJBG~@%bxgd64YR#HN7Ej4XrH&l0gV4|KIwt#BRyXagTH)'
    '=kR%1IF<jVp@zQ)MpZfJFsD*{VU`md1fDK>OB<=6g}lG#wMeKYm0ma_3ocjPEZmkW<gIpq1EBckNiDfwaj@v96Tu8k$nJV6lsXwZ'
    'fJEwkE^@hZxUs2w#+Y@H;N*$eunUY@U?URUv`Gk)cRB_Oy#mWuxXsr}qsO>=$BPh8oQYCqeRl`nPUB7p+JA@wfTX?nEtSjiA2SMl'
    'tx+04gsFS(YrbXPS#yI3;eftgvtb-v0Xr%?G?`p>_rpj|4TVxi(pLXFI5@1Ym6#ucra`a&-L|kIbpDsc^{Ti>nRThb?pJ_cv^G?z'
    'S{<N9r%Y!A#^g%k>3?&n3W1zQ9|2Q`kxh6|suJX$7)I+1nN~oU)A6Bh_(&QfZYYjgI+-N-x4ysXbDQ44Vm#)c39R1qLxHte7s8+z'
    '`E6oV$t+@NCWETKbeu#)-BIJ<^N|~hnQ(6heSmXRfJD0gXkp-a=ey?T1n@d<c<NV%he96$MjE@SmRd>Sa;)RU{648!rJg+TkN{e9'
    'aNBa?rxgDIrahm>dWq=rb9F?E-TNfI(YHxUtx3*=;hjrI+<v`q8<R{%UA$Rt0`QgNl4%)MD-LQf4u^88l)B|7^|=j6FU*=@{sr*&'
    'z8Dhg4GuG^vr1Exj+(-ZMH-xmY+<>SHRp3tvDnE^C^_EDZlMqyv;o3Q`0rw(2-mh0JoWf;V=`|no(Y%zInGf8`PJwYfq^E?hz;)|'
    'heK9d8)GKtq*41AiqLBcYGXeT-qe{Xd92%5U&9+RFi^#T!Xy2@-sCAw`(q?;S@)<Wq4ockH3HpMS5Xu92()}PnH+rU;IX<%<FBv1'
    '3!=mN0g7I7x3d7x>V-M-5FO_0zsr-{S@~)$r#!cR1IO-aHoq6rX`vK)oEN85zcHWwmzypM;QmxB$`9lbT$5dM-JkxlS?Rn*TxTRN'
    'GjTr`lIC!K1zOC;&|mFO>uLv*{H)_u&Y9zv=4O-!5AdJ7**kBIlgcu8i5I~j-U|DhB3+y0Xy%N^v@Nya1KTF~e#2?ROZ*MNZt3yV'
    'aR!%QPxY2jfA>gvM2iB<7>>WqRB;3u?2U&%lL7TBfG6gkQc_4!sBNftIR60z4Z9AEmHF3ESy-`*`Cs!nnX}Gj?UR<Z)X;ytr?FmF'
    'MO{@r{!rs2vyWs%8t=kO0r~siA_3P&%?_ElH3S1~7}M;ZW16fuY|I_;-vBs}RIZfx?#=5zkaLwYIH}s;KkcR3)0X`m8#dg+l5j)m'
    '|I#Fol$Mo}R4jQGdYW7F`WGvQO)UR6n}tSwQPi>nb3kv1PIP41CCps!L6cqZ9NR|H1p~dExllIE-{q(>@Yr{Q{`2(Llyb36FL8E0'
    '-Gk39jeOX3R?H)<I-y}UrH;FFSS8P|bGM=YdZYy95cEZ=?f0%s&*;4`kmsecTmEH=b_XBjZ3Ho#m3OFrB`kJu`t{A!;XAC<%#%hk'
    'lllRQ7jXanPPWQy<FX3Kc=KUFjqUCC+(|pWv{n7J98_WQxndeXDI0S&lgtJxIz1holMlDA$>g*$GcJOHGEANH3fXfG_8%kjM(zej'
    '_c9*;UHfeK2ZY#pmz%(!S=#Xr;Wb$!5!OU}ju2Dw*!^VT6J$gsf!wF0I@dz`-`n}eK&=Q<9sQ`aO&H>0DC4IKwL3%=+RN}u;f0!L'
    'idIKUwv#Ua#}@U5G}Cjqu#H-V0E4VxPwSBdY*qOYN=5=akx9*5EnUB%w2RIIDU)R+?+jgnn5|oh7fmg64rAvb_&s3~Q*)jZd%njC'
    'W8G!W45^nuBh{i~N{WnV3fYfda$2Fp=XaSBp>P0B5-$KE3l>DN)hQmvVHpfNgUbH#X_P8e>}7UN=3958lWo}RnR4Q@A83_+(QUe-'
    'AJLv3&dl5wZxsUHE9`m|Bo}aLuBO<cZV)WZOkp4UQ&D=tH!7`x1U$7d?DrQ#s*^UL>R?A|wzeuWo|khVy|Q}6`F~HFV!-2Z!$JXZ'
    '?5iwyXFBo*59MnIV)kY}of%EjYg9iQMmZFefF9H*_Nk9lF5!D!j7&O)lO(d>H53W5bZXA1U*<Sa*?;t)sWVY4KsAYvS8}ZxQB#L@'
    '1zpf?G!q=-n?Jz8NYhFJ3V0gW?wto=3!_5YQR|p=6$nE$9lcZe@z)zx!=7>q&%-?BuVmb^S!;|v6$i_Xoiy1l(rDSKtmhn<=96d>'
    'hE^1M?-tRx@j8FYoT$2VKb1kvGGPtBrCSp*NsD4E=gjUVM)r^|g%l?-TN}qg)z3R;rnJ|n#iHV{yT1>82lrsW8ugOu$1G-jXU4S3'
    '&Do(M%o<<~w&#>oe7hkgNDlI@CBk7@pI|+&-@7jw)zv_B=ZY}-7Yw-b)ZsyDft?FEN_k8QMp#89j-3CJo>g5t%Z{;QA7+3{{75z4'
    'a@|g;nxbKC={I!wLiHmQFUq$hC}dr5mB~WJJjb@m`C~drfaRl@I~PzR1gcxHNj%Q?sBLn*S#*AfK$@KuZ|V?(`LATgL(~kss42Yi'
    ')S?wt;kYcwnW}M&ZjBt!sgu_qlw0DF=WfQLEeaiw6Lmt1^G*RI2NfSADM;dlIupA%!7gL)$q*5~{|Elub61(8#ow+BD8ANt&Tce3'
    'K(kBzdQ-_t$m(9)zyC^qmVVp$#S8_=fkn<xxftt<#+G!<^Dq$-M?nN_9%}A^7s@xlgnh!WUWe&u*2EfUQN4q3ay6T~Yb+7jqnkrJ'
    'a04b@Hp!|AaC!|YsYiYXH>alUZB<rtg$QP6eN>{{22pHT+`Byj>cyO3X4BcHoXRI=_FwW*e`a&aM*$0F3YFEI!%pX>T>UKUk%0y|'
    'W{3K4=!@8lZ{9L^-JUAbkD5n*Fv1;vcWC&$lGV|*U&=lZ?fN4W{CWKHuMGaFt5afaVofl3JGb55zzde@Iqf7ooi*=X=AV}+w{~=O'
    'CSUpc&{7ILVUiq{fMS}lQeSB23JhgMoznPayeds{m#>{3kKqY#H=7D@PwA9NbXwt+caO_bH~(DbWL+$a7kT-y(qJ}hIZI8sfSq`?'
    'V;G(?RGSA9ykAYB?QQwqvGC&D2_=C|CM15Hl2u2GeA&s(%pli<HRW_Hgf9Uqi$qTDgS?@zj430Eao(Xx^Rchp3{o$2zL_wp^j)wD'
    '_vJpL9*%uOVGDiVqMm|(en#>)EMZGPk31zrt1^T_>(L~eW3pj}@CmYwxz)BMnm~d{>U!dDM9Gb4C0biObB+xU(7_qE+M9n|?qyZa'
    'kK~uv2gE!Vs-oXc)DA9vEqA6Qkpu-s$9AW|*V_JW+Cc)U_k8)=?Eaxt!b(R8;fBe8N9O`|f8>P>YjyR0CVNpsZn+qRqmj$(viZ@A'
    '-NO}I&oR&M;jFx@CTFP=!v{9ujxz(c!>6&pBw;Han2~BgFCtn2Ip}gpF`!w~+o8((x19CM^9Sd})HmryxcdtlRpiL(68jm?oDu1z'
    'e-fPSplPW}EQyBYyUMNin%O0V$eJEGAD=R?@=wAO1_%J0$>rm=wYh8>u2n0N%u=$7u{x)4D?N}i2th7^@JhyG{|45K2(hYW`0;Y7'
    '&&z5hVBDT>LgrpozDYE~!fg<;VJWf{5NP{cMl-UPr_S1x^b#kQ-5%~dj11BxEBkPzV=dFOVUcP75)TKy97SzRzexx{c`pUc!Mg1B'
    'e6HAU{PTv&=N&Mh6bI^wY40HvMT&EfZ{-NtnCAL)qI%tk%K)8)v3+Ge2ly~c9ctaG+Cif9H<^D&%K}l4m(^!9hP<S5?ThCNg_7wk'
    '!Xd(JrufE^<~{9U@^Gy)0_ri)UlXhE^^$g*kebtvL}O-&McSd*m_K^D+`tLX^_Z7eTylnO`;<LbWCTuaz@&+R8pY^K1_m>fY~&eW'
    'jqEeWL@=};J9B@b(jW$)p;UYzhU>f}#0Mq(^EQx3G#4EpWAjmk%w>3NM=2!H&jTq6s-kFItJ?0SSDx*!bTY=j5<qfl&@Aq3Q6~eF'
    'Tv>Y6-@#Wdj02GgDB#9Q1Bsqfw?&hDqvX_m&iD=wEmpdleEo~Oa5JBH=ZINQpji+*_^~1S!oP$_7)2aw_({-4q)eTv_QPI~=re?i'
    ')ucTj;=<^{5LwP0j%2iY>NIS7{s8sqc{Fi784_7xnhZG0##!dACb_0%{v7HHrewKH3~7wrtXm-*lglgY`<tLw<;;BEIICJdpp*zS'
    'XyC#ZSFCou3ojGd4J0YJWk5xO=8%0MNs!2Q1P)(_fd|ttcY$ieyYXsrWm`T_BNr-meS#U|&>SZA47yFQnLg<#vVL_dT`l6<C}^@p'
    'sx0eLC~VZjy^hHlfxby**ofio(f%i9fB)0rG%SCU<~GZV-+qiu+#Zx~cnF$x)ROzlK;pAEgTvNsZR$6E@_d6<G9-_h5?*&lj<Ozs'
    '1hh`8;vIK=pBgtVCNoXxUuzuOZSbI10%OhA5AZ4CGEGR9@4_=0b~(<*^gnsj`~n!ne6H5IlHGd<&&d7Djd|^m)(&Fo6&}BdbzL?*'
    'Bn@!><&{W0i{u+%0HY>T$*%NIT{sZ{DdFhGr`&fy3+@R%#HJ=AhG%Iv*n|AI$Vdsl&a|5p1pU#+;+d8^-Lpcz=ejn4T@L%&_GMZ?'
    'g}xu#@bV$a-oP<EK2~ycnfxg861l(TUx2;Y6KKZq>3O?)CEMw7f_&wO(9xbq`>(xDiEOhl_(#>4&u*Yo`W7hKXxTQ5fJU#OT<{rc'
    'n_jO2RX!+|)H)}XHiYCbc|3`kZ)Hs5x<~C%D{1CUn)+YnE;^l)G^d@YO85k(mw;5Ygv*h1Lfz?MhsIc)NRwi)gTrLs2k(U$sNg<q'
    'kl><|v6{|DsI<yPP~lWvE*J2Yt6%b)&x1~ED;OzTIW;tGQG}EU(g?=b1I)a|^(ybGIt`0~0<aC*c2&SElgl1s@xep!=nlC`*KBQh'
    'gF2dQj0W-+L?QQ`yoev`D~a+P{U$ae+F6_G_<<;7<>{W?s_Kas?`&VNw5ERdoX6keNCXDBduD(U?1%GbAKTMT+#FtzZRI00=xfFw'
    'p@^_-%e{WCgnI7g$JQ8txpO6&o@vU`tM!C8;07#TKGs&Ke808o%<yc$@1LvfON+v*?BWEPe+=g4t`_V_*yKDNP0N?l!$nD%H2kgw'
    ';(zB31&&mE-7*OEiOtJY1?>--$rO>x=5Or%4?>|Og*qzAxEz$C7Yg*de+YX=*kJP0&tBf9`U<$&dda7p(2rw6XO$=22eq)-NY>!n'
    'CY^SF*#4Ko2ine2yNdK7=vVk%6(l{7o6w9w!9Sh5P%NGzlXU*-pIjZoTkcVtsO)oCOLk7MN_eH#7Z$3IO(z<02b$lo<?*%owBYH|'
    '4etkCbDJ*wi=Cw8gQNG}xw{AvEZFjrXkWQ>G_CD9qY32zcsDG59|VLW8tn$n$$KQaWpwllUq?fM{9N9L65^=3Im$^R@=BnrUR~^!'
    'y+PH{BZ<WlsWGd!j}nzHYd0CFWRJNd%5u_W?40p<c&5*s24Hj4sC+%L79fubS#Jqz8h*Bxw@HZimjr5DuZj@;udutW4#lPp1osEQ'
    'Yx@)_C~yi4oBg_-r4_16_tBP18joo_LFHp}PCrv7k3M+pfsX@z21i_?xPSx;xg1etrj}$m^_RjP(d1s+E7f~(j;R+U%^Y}Zzz^9*'
    '<Yv7M?_>QugE~1-6_E~?NZ`uuqME9c5`#4T*3qK7U?7qAe6Oc=VIClqk+-oqPC@`MnlGhN^1lVfDr+=ky7y`j#z)V4a<@)%K5>;^'
    'Q{|lNsTB`kMuNrOXN%EMMXeFzu{4wPEMKQ5Vr?MLDS2a_F6CF5OPjgx0fa~=j$<=;e9ajox6O02K59`@{eOobbBjs(+fVyj(~|}Q'
    'aL0E^jSN^(ve`ppaa-)&ppW-7A|PONqbPrIo^n2*bG_OkNkR$0o$4=;@6<fif{EHy*lh+CAPs~p%p%W!Wj*>i*4il&ry9KGE-EaH'
    '1*PpHn{PSh)ZL6V?}$Gv+#fpp2l9EsE^>EMm7Yu7h!`vhz5`Bj#UFQolmI$0d%D6fdUL^!e}sAm1NYw{Yn7G_vEQdAY#<OP)d2A;'
    '(YEX00`{4t)i0SSO!86%Sf>DZ0tE7rWU@;~ed6**HSsc9|B4U?2PjS_8N1Z4*S(V^7`LQ*PiKT1b)ak(eGvUenoeF>`rf`i=QLwx'
    'kjkKuXTS^ovmr}1@j|AWkINc^29_RcR29Qg^5}@?XTrA!28(ZdB!{YalW~>YE;17Tt?z<mLp$@30ow&7I@@C^MYyz+Q*q==nt?bv'
    'ld({89o<N^dR)CqeCuvO2W0wtE!ag%Y}FP<3OF>3sU%@FNl0oU<ww^IwLz%#I{SoqZlJ__ZZyK(t{ao{@4>#F!VF!tdUu_Yf6n06'
    'KaP{gGi{jUei<$ND72L<)uM}0Od{K@x#H+6Ek`<_i^Ux9#z%e3K+$o`*Zz|%fhts3DlDW(#(ub&zo;qc)Q2OYNgfjI0Ca-1O7ez1'
    'v<R&Q7B_I#ST=R-@)m#JOgBE&jdUc@4=$hvr1=C62$)nSQNi0-e7TEPPF;Yg?A9qyMH@M%<YVB}PMakF0V<)I{U<-=dM;_?+gK?c'
    '5lf}6;j+TCq*&JvTEil6y!59NeXD1M!%_H(D-PAlo~vnBF>8{_i>o<#huX~oWQwD2!$$qS)gvRHb=X9nRhE0p!zqc_kF%`okufm6'
    'n{LcDALGZ(LB^Sp_NCB(oaj!G&cwV33FkxEpGTWKa0>vAbT8xWS$(`rV{h9RIG0212olN98>FXfHKG(cfqYNd5u>yO|7g=^Zunb$'
    'KseA40T_4*U@Gbw7Ds>~Q%|cV5lEDw$UI?rWnf3688(tUQ&&6Ap}_IDaKtjXvj8tTXj@&L<L#qTSaYO}hY+MRu@Xu%eh~MZMvY9t'
    'B|XqT$;ejj1fJ9R<C@@C6u_NSjVRxgH1*^^6pZ~|MxG$*>*?~?_83W9(8g<%Ob=X}sHT>)mK>}WI*T5^BwM7?Drn1%o?ICO%zaAO'
    'Z5y0B;s{HHNvY2AT8SbHQJWYWRDOb&q|XuC&LH3$JUk=?niU2|kR^b*=lADp<ZjEc0w0N{F5Zc;Y!38eRIrv|2D|Vf#5AD@0n1({'
    '?_Wn(s%d=++pYNvx4xUSp6+?&{?3hSftEW-PvrZy^9sgQ{+Ls>!dlC{nMWmi`omG|Z8Ha{6;^Ym>_S&enMQSd1^+!0FSQI4Fm7MN'
    'y4*^;ZI@C99AHl|55!upZR7VDp?!$YdFk(T=>hOH6Vn+CAbgM-uCrux8$7j|NiS1x=t)%W%>^tOqqrhZo;xRrVg(`OQ3wf$ESnjX'
    '9wMCh15H-Hcq)Oulv$N(p&q~KLA>Vh4f(h$CzmA00W4<(biC}l3v#v<pW;~?hMc|W;U2g+Jr`5N#n2R;3DFaZiW~Q971grJcurQH'
    'h1uOr7rrn_xSHmYQcJs~2&m_GF`I=e$qXMMfirUTc~}Z4PCHet@%K>Fz|h*rNu<dZX{ws{n8(s2`8uZ#F2@P#)1TJ)vL@&pub$CJ'
    'C<H(`U)GaTyy6XHa9Cxx>ffDt$1N0+5dh|8&*Tc(+I6q&v(XrNF2nE#J@P|dHT-wk*Cbz~7vT*zjCg|c2(jjQbF{ZWpW2Hcgxjq+'
    '(D0X#{?}(UM(pGk`pz%m-tH(DM#Dgj+|a2VC@(oB0eU|Lu5Dc0ow?7=hJ1@!GZIx!C#)ajUM*~OEz_n@f*d7J)TInAmTPE4VL@T&'
    'vBx;3-{Od@v58Tb+AJ;Ies41ZL2X_=-;pLvtVs^n6>-^<bmeAPbu`f;y9CBwAJCeZX6n<`r_5=CNbPXmlgs1e$$AAY#ap?6V3WYd'
    'iD{~AgU|}n<%a`YoQ`Z8Ibv>_+0RvqI<HAt@yKdDwvHeX$`FT<1~Kk<T}lylku7e58rGY+vMtm$r@0gh$6!o?w=>Bg0KcDLW>oOW'
    'CyOCJjj$g}q^<hTg5G*+-)E6Vq(&9yhtHKq_`kCfTi6QZ=zW4GS!y1n!z#10?PIpMq`rp*{!^ApvFb<i6i|D6f-|5iWz~25<xUHf'
    'XbJb(uuN%<hBk7wDc6kxX)fpXq)W>pM8%vMm-hxSTtrh++jHj<seZ$Q`a3`ZW=@?X^*Yl!+4EiVZ-G#f)!z>Qn~GdF9cnlaistuS'
    'd|{GiQV~m2DO=w@0OfgWH~4xyF`GC~l)1wmnp#^?c(7k2=fzS&ya41nm$_0wHQsmY*mzx*atng~FP5eoDBxDRWHnnE^)f&JL9B!w'
    'I-j*f(%xs@7XD`Yw7(V3TZ0w%WGXRM>04fdNa1Rr-+<!srl4>Nk8g-Vx%WW4<4FR#w2b!qnx1*(Tt=ss>Nq9;B@36=M$o89#%ij1'
    'qK*#+(FV$oRavad9nQk7PWhHRpzZ>crcnwDAp7aIO8+#(lL49MBXS+!swxXsIVIC{v1(V)+BL2>kra3CMP3L?bx{8FS}0+;h5)&8'
    'zOWLhf4TkQr|f*wJRH$R<o>W2(cE6fcQ5U_*H8w7_2_7>e4WWEJTKuqaA!`3ej1=w7J$}Q%uL{89vgz5vbcR&J(B;?4W|q0Vpzhb'
    ';Y>dOjl44#nz+%--YQj?AeJO=!gj)Yrh3z<bexnx=8sxz)jQB^C-bPE3C$n?u;A(wYuM=melT0)nA6q#_?u<_B3K?x3~i%ic0mYf'
    'ng-4RG&wBMhc4-e+WMvOD2<WA?OU<}^Hj>Im7zZ6FXjAD!F~*NIEnx(^rU#D#bj{);I$3|2r1RZf2Tpa8vhP-((mj_4{rv|pV*4D'
    'y@`W8p++Sp)FELF*T(lio%}Ynz_%?bj4}#~rsdJ$!cApT*F-}pUgNT;L`){<HCWCDhay*R2U{B|Hog=8tt4r*J;x<GBe7B5q^NfL'
    'ql>c?*4Q6~jMhlZ1ZN}QXWxqXLmdDMPQ)ZHI3pIlQ=<^{vwW;!9`6```ZuG7VO^(#69A7M_}QBdB1XJmHrTS92!i%Cz^j*TX&}~o'
    '^@6bw#QM8%H|kutMT@uck#dr#K$(n&>PW8eKMca6`@gMlJ-vmW2wpieokRB>-)D{SqPrTx12x@~ozs=4o6HM0TkAo8bnST2wt~pE'
    'Gfn&0V4Yvrt4*_UzQ0J--F)A5Q*&g+o0E_9Aa7wuwG#{IYiTs94EMBMae?5<#Kl?Gw{q^GNSWh!WAC0tZev<jyd;8aXJ@JB!Pu$i'
    'dO!eSKb*f?_3Il9P=1r?IR`$^u;;huZPy=79n>N)y%o>8;6fnX>7?G1M0=P#WbC+6#C7`Asd4}bj_8CHc3z`&VN=rBU9ohmOCnsQ'
    'C4NR#Rgy`y?zX{blCVPe`(fW<NF{gys62{4nl`21%oUfd9k$?oXM0Lngz^p*V}hz5!#7TL>AS<YX*?1!JP2T4Q;M+Xz7+q9)KcMX'
    'eO_o><TnG+7t#rh`$t7|677{8IWt3u8T3=~j&+;Mso$5^TdZAYhejPIJ8d<p=;@Lo+6$r$LR;zBKjPbs!Gn<0mJSe-N{3fv5DX=h'
    'nWlw_1Z)rGo#%(J%a{Q5f|~K5?4!G24*?eOeSLuP-2&H3l3pKi)?9@0;4T-jhHdHDBKfUEodN^JhH>ru%^pJIsnUlxvu2mTmw)sm'
    'ZZ*ZNyY`Y2p6Uz^P^<2xCQ{BLk|IU;gHcH$n2Is2-WA_No1NQSWZ5SD>L`4tk1OmOpJ#Y3korHfsf8a}!#xBfz<JjObve6T;}xYl'
    'tB7i|pMPpGB~fAi-d;4hmYFlV%U*#dp?H9Zx2<!TyW^@IG*|4&a`qtFvZ&$!1ztMAMhW_KYG<YfN|u~|aucBT%3d4|!AFpa)GtVn'
    'WTc){N7^LUOp5`%9m}rYMxH==cu9mo8{fnfG4;8p@a-*RqoKW!uSbh^vIMEA7<NDy{D2V7q~Q{6%aqMqg4+SfJC0P!MkA_;D=d!0'
    'a6=zdr6@~a{F7F6%M*cvPMV1hA;G!$N-j#^ECjHV47p)@?9}PHau->gwzE;Q{zRyvv(qAQiP(JEeS)>E5Wr)U>+LV}Q>e{^diLk('
    '#B=_i%JqA;0{}!RBDH-CoiR9$JMbR?|1klezZqV(8)U=oPnHh}P_6nyn9M`q0kxbsaJ5u0^;p2qpy%b;jwxSh%YhUH9%sf>kP?n@'
    '8e$HAxpSm##R!tuY5piR#jAD|EXiuoVr%B{1}ud0dM|w5$v&n;H!G^LNqLD7_G|S@wOPz&-Lv9wCfOvg`AD)l1J2P~%jt*RgZF@<'
    ';Vd&>EfKK1S)iH4r)~G{Xwb2Vr4!&Yh&*VHr~+7sBSFOR-&vA^#=zpidTQTvYw1s3I-4+}bup)HkN>I?t9v8F8NDxz!L*CB51*_*'
    '%4JOOUL}Mj(1PyfYk^@|#Bf>BTd5r9_3Sp@d&aT}^&NU-cx(;co%$QQ3jyVP{b*9E9``E!g6gFn1g`vRc`unAjCzk@D=~jExhLQo'
    '!hdRdN}F$y%O_R7F&D%9jz&fX^8OmXqALM^;Xaq?_JrqE*{hlifqZ6X0VIt;1+KErxm(&ndzmS1HsT|8Ld#E|#E_v)G3lzQWdsiB'
    'mnE)Xemtk6#bb*!&5~^(DC~#+GI0T3T3FiYN>Qq+P0Y@vB(Pl`Zv!{lw2pPhT&ig*u7PD$_riwXY2=^=VZyeeeZrbzhMF}*e%g#F'
    'dqkr-;kK^T#(FNUmvh$~IWZ1zF^K1=m_<LM7r@K<Hdaz>X?l3=`->um8$$m-#59_wTE=AeTtkUchVNJBF3M|TTzQ$akW$UqM(zx5'
    '=Z>WCmc?ad<B%m<G7k4`0w3O0cnmF+WLG#E)4E<j54(>h`aMYYhhLHCo`hZDeTb61W=IkqwyxZwc8+I<%beEJli^16rhPND&G_If'
    '3efIqs+uWTwPF+aJ1$LwHNyJAb@k%fb$ag^4_l%99Bc=P9;`p15z|(CqK6Ejm|qRws<;ytB?@o&8RhWjhjO0bis2k^01OiW&XH_l'
    'Hb|po%5pKIt>)+Lx8E0O;74OeK4L+#RV-eD#+Kb9=y_EWG18HgO{eV=K}UAu<99pzU6<D-Q70MQO?uQitavnxGOu&^*}P_H?E(t^'
    'hogxjT5jn%(m*3tHr5hG9}I8-{%m?RvriiCK(x&Ys&EivXyUaGTA19z4-5r2qOM1Z4EuDxP#2Xx2}aszZh78fI0`k!<B(ud8}6?i'
    't|N%2>^69bv0#8{ky{e!{i3M#yf6Z4Hu?DhpUQtRsIYAAMM7Nv4*P|&ez4%UH$v?oFA`1%*}hXKHq7d-Z(>4md?PBidc;tt)fG}$'
    ';j^!_Q6l1c<oxC4$ae;`?H7`ZX)l>Jq!$=eVF6SZlit^qY|H7%lgJTc)ua)ryL5?%ndy*}({=pC>!=))S_2#d2mFrd8eW#A{sE@%'
    'IYMNG^S<k|-iwXNS`z1bs;!Jv7}oO}&{kCozef#_iV@2s)(zL??+SrIKRl(x<rz~AXpS(CqJ$t&Xa+SQ{gT<rx)Y#}VlQ2V_6rc&'
    'Dt`!1XHo4|7IlNvS!z#rWcR`rzZtM5R8|zv83Twy0u&RKY!^C}E5Up)urpN=oWThL&($#@9Rfm-u_e6~c<zYPXIcJJJb+YzUo1=n'
    'LUH}-UWA^@WS9eg-T+m74_Zu(>feG_cFcHYVE!>nk94=Q55Ivt(dC;6E$xxsqmNsHv%De`TW$J=Dv8kT-rFRh@S)(O(p^^KWooA~'
    '`S&_xnd`fm`Qd>QiN7|d&xv&*4wSKNhA|1%6NYgH9wx<nC$l0S>f3f(2$5IJJuFh-hu}wISp_|ZV7IGRq~%GkD*!)Pm4L2F*=~6_'
    'G||Z+E61+Yn(t}|SP`{1o8;D4nn4&miFfIpw7g}yqw(Q?2_GS$L<-(2R$m(HFmsA9x6udJZnA;hq>Hr}+#gW=;G?8o-H}I0xUELX'
    '@rTpFIw|E$w4DrSTB1*pZQigNk6*6^=%WYWaQZ+?Uxw$wTg@TUO1GHka2vM$u=SrI#R2w4y9h5%$5etN9ti|eK#cMX;4*bC6k36T'
    'B3<Z`T(gZiPUdrVI$3AM`2@ijCTqQB&mMDdsdM^(Q+C_8;fqzSzjB0swq}4nRhW&3KZ@Oj26X9iQ21e>5AHXNZP1qACt1#jFu(We'
    'pVoo)74q+Z;8AMLt$*65HQ4fQs$fE&p$qdT@}NYOuVR1BhTT!DtD(C!Tedx6IW?b9OeJbJM0oz9>oA?XP$rFiqi?t{4UxbRG-km-'
    'z>!<zS<xTDbQ0Ru;+R}zjFKt8$stShcSkF=w3`D$xN%Px&hsWiMEm4$aASZ~>i1s6WEOnx2N8D2E!8n<00>iC<K3!LUG0&8n4Ce*'
    '7t|unlKcl$J7`xFu+Il_u>?wxT-eMsipIpuor+@8)jRLDovlw4O~S$V?Nz(YL!u_e;$q$IyNxC2D2n|B$ExKl<%NkdwuEbF?YDt4'
    'u*>BuwFU51a3{@<kwe5tC|AC$lY{|=xiXxC*;$yqd|(>l(T<te7Dcr>q9X%$+0+T_3lh<$m~UV2SZ?v5;v-Tw_LkHTuN2Ws2f(Lu'
    'pgCvN^MUm$V16Fn5$D1>YSWOb3|8Sm?8y?tR`?Z00GdtI+CvRwrc&PmES&)2D!>~Z*h1$=#^G<%*GdDvut!Ok=)hIftWer$6YPaU'
    'c@VZyj=nEo-aP0=X&sA$jdn6zS8lb156PMQXx;k_tEB}(y6xlly6G*p{A`ALM!Vob`f&cSYh(}Ylb4v>(uHxh<RL=#l|iGg^eAbU'
    '*!aZYL+>_Y0qU9b@K31=N*W%7np~NLWo(OHx&H&n*)da()V{_96}tbEPXqI5aQ_S>NB{j2V}?<{x@o+&l%y;HU7+PQsOGN;i}cmT'
    'Qd+giR55If3}2Y)y;3%3mE?N3j!;*%3AG=LQr6LW{`wSqDfKdz7E?kviHhRXz+<lQAjIUU8;_MH$hhvRSl9w7X#KnF{^Ohmfx3{5'
    '23yKF^4X)D_S_T(BaOeWQ>0`HmhI1(e{Nn88&kvFw_HfUPa*wQtmlZ2`@GLEKSK$u)rCQQdAYnftFHD|;Hturt=C@qU@}j+GZvm?'
    'PQ``k+B20e<U9+acc;|Yye^a;q>4((02+_fWH+6Mn`xKCTPDQywv@cNt4x6s9LWTKU6(}@CMHiCD;{>wY+Z>1)oOk-i*iCVM57Z?'
    'sK<99<ljDNON=``sf_f70*5^Vvr*d#Ykbbw?wu>5Q376Tnk4$~HtguDFd)A>u;)1Rc)2*d=p;?4N({VRI@XZgxT+vX&fw9{T%c?h'
    '_8KGOdM8q@`<{Fw*llzupZ{tM?muE;A}))doZYC~;96oTG6P9@NS&h=BH7y<hvWP81nS?S4d+zvil_mg$K8N-+WS_VAg?$%g6(aU'
    '(oxH{U1TQfwzRxD$<@X^U$=L{$?`^ZiflXt$fk(LW^ACe)M>F&d*b77ZhZ4H_=fard*yRcajWf_B7X@>CfBWzf%-*A2Y4bAvg9;-'
    'Zg?Q6h$iOFopAQ?eTetoY`L<zv@9^F#eW=h51#rIT%A<~R~g!8oL(RUm;~{p0J0qjn(8UAmPyyJCbQ`1`Ayas9w~+kwm|y>q($oI'
    'Ci0>w(~dy9K9?Z&SL7j(B1ue$+O86!9ERG=@AY1Z#`L{D3pqOaNUur4Gm-xb!ylfx<AGPc?1C>My<@m%5a(<cG$BQgBF!f?w9|b6'
    '%)Jj<_^6+?g<{P*^eaE4A|2RdID&g^<9VRQ7k^QpcTvLvJPtNO(xuuZ!^+_|sci8`<U_64^~PfZ^+a$kOKn~Z@QmZK>OP|+9+#!L'
    'Gqb-;xJtST8pj`&!g}xnSVjI-MEFlUoM1mdn#6RVD=~>$$GhV45onUUIce(=+iES#OKDqUa~J&M*lE~TssY&RAs{7>TVa=QLSL0+'
    'c0b8R<(ofHi%yHbeBtvE4cr}dU1r2Q>;1r$9In$K-e(46$~T8I3Qw+QN86V(D#kUlD~w;?tQg$*(QNNK<&AvWvBqDysdM5vi>tZ5'
    '5X8c_m00vB#$QhhBU3w|0|FvtSoz2<!F!I)c+kR#*v)gqJ`}1Xc3DL+>4%-7=&|u!ocVKD!xJ?T&g316=X7q-uKb(uqL#e4U@*6O'
    'oEnq%guuE_Ly6Gp9z}m|-9+DFnB9k~@J!Mmd7y4|Kwxk}f;LRa9RT?7LXn#>j{od~$VI`(B6+Rsn`6VQ87M}P2!#vFIXP8~qhrGg'
    '9@(M@LK{j@ob(RoMcf{X_1H1Q-z@E~d;KxdYkiF1VH8Cobz(}U(>_t$xIU7xmwK?hO}h!<ClnWc4)WMWvqO^<9?%DW$NvnW@0W_`'
    'O|DbuTR-{Vx9Ex|GQR{N?hF3fj01irjB(ZjjI0%;#ATIM=yAv6fqu<d+?ViJdn(0(drj1HK2d@)Z3OnDaoP;E0v9gER_dm^FPxW{'
    'es-%tXd${wQL0hu75uE@+nw!;f^-ZNFE|8gKM>N-7))#HmfQj@N3?BoABW6oI6n1!3KsUKJqE(SbZ3kJ+LPoQin6S`Tz}a-$1=go'
    '0g_)eV>ObPF4;RW64DG7P-j9EqXm;Ys<IoP0H10gk|-Vi_yYf^_TQZhx77yAA5eL~&cHC`->1a@qfV9-b}X8r#@*N`^-bkyOvT@U'
    'ZNg1PI<Vrfi?-~c?$L{0y)nvK8D!6~sH&-1$pdaTy}G#Jt@RxO3L3i2QKOH%L&@?|cJsF_db4HcQAqCF(<obYi0i+ujP9mzS?_Bf'
    'n0Y6<?6K8}X8CBywR{d57m~PR4&FhwT&^FjmbAae@p~CA5G=0z{g5>!QXj*KscDA5{qQn|udZk7+KvjprIQO-MwmgsDY7p8*v&Zi'
    '`3WPMQn-{^yJqh#*pFs71kcJm*HZkp*QtS0W?>7WM(q&8W*;#s2Nv9d&(NJTk5&ZE(uUk~-ET3DV(JXAw+EFi&bwkjr%g0D<ED2A'
    'o<Lm-CFs1R5{&CymId2@&R=**n3(!M`1}YSc*N+JzXBZJR*AUI8zE=T?$MKv@Z<<7E;JLmHN^#}Wz+4<c6hQgLZ4DKM9szIJZwQd'
    'J^6IddQg_mRAj2k^V0gT-uloW@tlrbb7+_B5eVD2vgQ_074s|#<9>`N^<0|%yGcMP!l<#LwyMv&YAxCF*@IGb$o5%CxRk7{2nvv7'
    '=r(^=&J@6Ky#c=ap1v!Mf_`=2<a|M^f%n5V$|O|mfw9nViE)D%i4UpbYBWX$ton4PY}T-F!j6G$m$mt#rU=zHD*+Q|UuR2zKu*A7'
    '(dEncA32d8yRtz#b_-uC=T5eEeHQu+REb)fEtdR<+CD`ww=*fWSJQQFztoTR;pF>MJmg%(OW#twbY%5ocr$^x3e*LRIWhg%K+2f<'
    'B7?~?nK*FC3iRk@mDK4t9cV(+`8^nEte*J=lxF9!THVqO8bPCZ^2=6oL4+mk*&|%|i0!K(<x84StZO$POP>t0V%-M(OGcfpCA~il'
    'gjnd$(#06yk7cGs$s^^%=ez&z(4Q*GAB9`1y9ut=dtE!bfuN~phQ?8i!tiVYSG9`V8H4!I>$M64yX;WCSc7K>VhXGVgW)-W$=DX-'
    'Et;+n_sL?f%rv#JE@XoF?^mx_s+bP-fy;)}KMr37ZB6}2I;knD@PPWlU@WB2Qzn?N2Do3pj&6(XOLJUiX=^f1Gp-uwP;r(pMgc(Y'
    'kbV+SvWFy5H?(1?;BlE#_vNc*d9#K*f+_U^SK~n6D{FXXYa;v@1_qva4RHi^qL>>CONmGRou;6=L0WAK0ooNeGFy+pbbJt>h0`1#'
    '0fy#`RZgS|Dv_NSg!JNXa3%SQ?D!f3<z|@&>#yqw6CNM=Zm<oz)n7sJe7pDxS{)eS7K7BIS<8L#&?7XiIl=-_Q(eb-yD<pR@@9Cf'
    'OSwj(bH2=4_LZ?shUwK#g19x1nUAL?z7m26I(={Qr?M_3<o@hOnCIv(3J4TILn?#qpaH)y$<+6&D2>tWEki(GVYh)+lFRwzWbE=d'
    'ea>&dV@N0uVvuoakK$}MIbu)&({jkZI)L8@(25;3Eju}wDwC`Ps}kd`xso(Bv1g$Qqu6DkcWbzxiZW`KD>Cl;@Z09ES*O3Vs?p!1'
    ';;z9MireJP4UWoNX*oUPzSMmS;MGyHu-yyBJVI_C5Acc_&+k+kRY+Y1e#gIxw1mMnWg!;{#U6Hua(M-CL(>H2;b8=L!coyZJ-2G4'
    'e1zr~j%L|AwBSFlEuMCKHQzU~f1G~uacQM7&_GD2U;q`ff4W{;2u9U!tBG6zc#n5n%yub9Pw6KpCJW&z=*`uM2E%TlOFB1u2>%#1'
    'DO;l=6wWJ6PVd4&+ZAzPNf1?r^;$w-_e4EK+#Uq~#(v80JwXDol<QVoc!VctBDG{GBaY}ti#Vs&^ntNq;F+$5f4;M!ld@l%K89cA'
    'HNx&o$CYFOro?;%w-Q+}DGo$Spbx>Fp2q3qCvBX|;atc#i9S-_3#>+8ifiZhE(JO^!iF`J6~|yg*IP)*MFP@-Fm4=u*?&>d*H4AW'
    '@bq*M&O;e68|mmBfK*h2eA{;|$Za7ttg9eMBa)T}R_Kh3FoSLz=z#1-H50}hDIrXVpv)4lD2iu7Y=pm1g_Z*$J!jj{Y<3M5|Ll(w'
    'hMim9e*t()VlcT_?r%974AB9YNYGHsHw09co1V>_Iu8x^X+{7b7lH(WPgjf>->&09td<mHzc3UVuG?|f#>3`V7cfxz6B|b^AURh5'
    'wX%`da=ap}d0W07{Zh~aum@aH0L6!#KRH|0N(T`O=bBYZ22Qc*)W}<ernfdxK=6QjSfM{?EbfT*bH%0zmdSvm<3+=!T!Ad<J8PiL'
    '^8V4Xa8FE$kzg5Bk@BrA7bhq=qD&0(A`OkdqAb$<l}^n@guTn4hs%x+hx$tUH{f#~ho<(2X~hYKh{seV^?0gE?6>{qec?tzFoq(C'
    '9D4OlqST7d_t`x-Hu@N6xn<w=)$*W@`i>}!c8XtB^;@~x^q?z;BI3$Z2t<7)Zyk+T-AR2s?GB^hRG7!nO%pLGa4qoTkG<B~QrL&?'
    '=XjHwK{w=>sZkbR(B<-~9Oxy?ffpW^wEFK0;xn*{mye&RjYQOkSD1a9$7Whpr}0s`Hn&rSEm);%UT<=tvM8H{ZBZ{v1B#uXFh@hq'
    '=Ql^6w^7Bs`nAb<^Q`{{x=nD|{_+R^OqZNU=Shy@ogkASHJzk8yDE%YurIH7&wtHO&%{>%1zP2>0k!-*-kGBv)?Pb+t>;tL=Qa(n'
    'D5K=@-&G#O6!9+1#F8qoPkz65ef1&NoefGBO}nrB9OQlT&zn#^Namqfvdc404X2V09a!1?EaD|#*jGxrRxTY3G?@nSy9>`tPK+GX'
    'ao3k9Iut_f?lqwjQ~P23dN#4oobaBk2Pc14<>Cx(!z@%fpl>W%ZjpwVBJ;Lndt_h>A?M<XH@~&hp@N_;Rt{tZN~-6m;s*ZfM3xa@'
    'f6D-t42i)%Y|>D9A}1!3Yw(;s_Rw9ktUIG4Z6+3Dt*~E{&Wqj&^E_%A3!Xb*5UYIBeo-H--&h$7XyDar`gO^br@0>%3&7wS>*3n='
    '@RtOG0q)!eG!d^1U#cl;2qGF_I^3pFy>Hj2zPXIW>XQ>6_14ajgW4Am%L=~aYf&GgQqIqz!m02^)l_II&4mrSiNdvpCN})9Ib6<U'
    'u;MrI9QG^VCbj8U^;+In4yYx241hEw6<~Ouv}3jv;=|nLw@{+NCzRybo~+H5ti&{s9@7Xd93R(7p#pTnWg6hn=zSZ-D)$8&2O}mm'
    'x?Tv&7S#5Vv%SfRplZkpH{0oQ+?Y~aJo_)c17`4zT3&M2lw_`YfF@2NM<Fqd8mDZpNCjHCn5HbF%~&6q4-bh9maKj#!>Pqo{FQ)e'
    '(~l15N^01TDZ$28$K)DqpuitFN>kj){e6VuSjb<3UrRajd=MCG<7aTE5w?4r8>v2CS#8q~k}W>%dSt0A;a|}5Nje68s*o2aY?{~;'
    'K8rT<i#on8LmuE}`J|fXc{#`WnPNYt<s~}J^R29o)7i}uk2v<8oL})pc=|UIn!l9^0cpT$*ZhFXhqz<{d9&RUTS&C9K$LeA2i4S&'
    'HG2}nVaW|vqj2<WOpZ(#$}lYH#CBe!9`i6A3y~Xc9)lV3oIQ<TzM;?+{k?eJ|J~~AYg;-}dOpGv5Rfn#hp82l<525G36G^fx4i~h'
    '|0uh|Yf~$x0NvkE$vosG%&HYqCApf)4$Zlz+Tb}{9;Z(H{C1Yp)H#h(n(Zmu9KU<dC3pQC2S~d&%cCZvXuWDbE`<FODrw~j_45Ql'
    ')FsDQLOsG<;wfeIRG`u8@jn4OHSSWXM|X4EUkY5XBPyX~;<W$o{qPyq_1(pVpgCe+^7CwS?zO-Bv$4SFD5ty9YiS~jqtM%b+`I>S'
    'apma0%=4#!8Q(Q}Q(cd<(*AA*aOzI^et$!C$R-z{r%VEX_`09L-v03mx`AD&huzfAA86{3;u1KRxabG0jO}{Edo@HE$YV`uz4b*N'
    'rKv>;2g8JoRLhA@+{XR9jlZ&uDl+GVS^3F&+DelUnooavz6<q70S0D^D{*mHDm~K6)A4+eZl<Q7mnVEH@84w~e3ORNK1H8H%_6mE'
    '<NG?3$yI#$!&glq=+-G5Rb1mLsuZFYBQZ2vAkh=SKn(Uo_$<@C0_q;v{@h08fBi6~ff(}t9-bJx-_BTVB?iy#_?*y1zHqOhce^(8'
    't?4!8-nBiyM3^;kpGzc_9NBY|!KV$WYyUIRdPGsaWha&EtnxENZ?vP7dP|IX+JCeIID4eLoj2kcSe;Wss3uh;Oa6$RQKy<a376aa'
    'V7R@W3+D_NJPlGp<KSL<^q2q(Yirt}U8680*9)srVe4kBbWDoEa5{j+CA%)okl}020gI&?i=>J00|IpZjA!Mah`ZCWg`t1GViiDT'
    'ALe!9{z@Xzfe4)Avfp)l>P#<@k@{a^r?p9B%Oj@{FxuP{J0RM+fbm%nn51>?_|V-sX8s?5a(a?@6zIto)V6%82xS|aswbC`!^!S;'
    '`p1%vtG0*~PQiz8VE7+<qVV0PTjzuIH1G50CKJSm2>_!WcEk1gWG2=JSibA<vq6P3;d}<k-E08eH77*Vh1tn}wf>OF$PvMVoWObO'
    '&(Y1^%4n({Du<2#oUQwE=Yc3-=qFNCxtK}@^Ri}!{N2`TK+L?W#hb4W?a0R<;iBc#$2FZoZ#2}?87F#4V7qia%&@}!a5?|t`!4Vp'
    '&?%fR41Q?42NIO&@PA0m9hsx=J$6FTp_Ay{O55nB-jo-sCebnQ;oR(IAl#yn>}eZ0-3fropk?uycD`irf|ibc6g2^o8AK$ME=vSW'
    '2-C>o04#-tLf^~fO+gzFVgdG`dE}Um=hO|RiN^tMg*Oe!r7aq^_XDvyCfM}zm1oKM%gQ-frP|M<)6E?v&GoS%#OthQ9V11hPrjnc'
    'Ho4t-;!htpxk_|Zgt*Oy6u>H*N0Hqj{D`4}7FTaTpe=f}gn$VRP;0uvG9eQqt<I$?(y1MkBPZt}hW5Smn0sXD(K^Un>-)@y+5Q!b'
    'bI4~5=(kBmsjc8_2u-5i6rZII`#}1Xq%pEwVQZrx({aljZn5p~y}T8h4#{HL&aNm{BQZg!;VR^D6up=Zf-zyuDab#1uf(LTY$IV$'
    '`YAF{H>WZpw7O7jwWP0{mLewaHj|Z|o&gnEN@bXet+Cb{`lSaCd74-sN?o0cm0>&wYd%_~ZdDcsu-e0LAk^7k=M%eHMbQYCCQ~k8'
    '`T)FTaQlEcVQ-or$90Ty4Q_O724lqh^rm|wzr=jTT`fK?5A*lW3OY2{z@R$RPGMw8{n^RXfI_W7CM!<}2dgLhGT93{nsJgSswkhs'
    'q%&KYDBWpPZwA)%=f;QVO8aoQ8~fpLRquh)S+7lMz<nljUfn0@g(*y&)OeJGL?vvT)hu(`**oicI$=ueyE#nfXSKB238tEF>f@w-'
    '3VJHsEKF^s>Spj^hQ-CK56hlHPW9ldwj;0N=XhcZ8$jEu4G>%W`-IqRtaXLZ(-&DKiT!?VH9YdB1Pe4hEDPmD@j4;xQ-QjjD)CJX'
    'C=*;~9E0uoc|viM17z(7Kwnj(M}?1p&j!$u=1BaB^?!)uLvnHCwdrfFP&{@z2xOW)6SM2Pq5<f7*p3^4uHcjX-JJ>nJQLR~Rnem5'
    '*=Jn(e)`CK4@<Y+)w+_=)#41aOsVW$(Wve<Z7$NCF(QXrws|e$NJ5j(P}Dt8TB4mMk(y?EYLOXfXdK}k$gf7K(9e+7=BDx@9GzLu'
    'pM$*;8-YMxXs5g|?Sf0HS1NsraZm#E@2q(I4oP}-{?8^}d+*G1(ul}sojUx_8z0-2>$==vLM?OuPCY!qbd0-nkJmVI3OleZLj0rk'
    '%IZkF9+j!8y1~P3S(D}RYMJy>c14w<nGBtoj=JFSPsGU$0I1@~_)L(YALUT>&b^1GPW5oAgoBv6T|N_qmHaPn!)N>BPI1^BU-6dh'
    'N9?G`8G#nUb?qk(Jo~|!W-MRMEXgbjIJU0$Xi6J0tzR(mU+#6XMXHBn^kMET?)a4YOz8w#m*ddBw;3<k(zt7CYc;!3-#8uw67<b)'
    'N2;?=6~{YkSM`1yjRIrk!U~?T>Kom!S7m}erds#Qu&%RoJ0)`+AqsJdJ_mYW+qwQ0TFAQI8t>Ja?%8-S#v`n=LCE{mxdF;J$1{cz'
    '*jJ<;b?%E!`I}M&3P8eZB>Ll~*$6`sYl`+*?d?;ll7{dFB}dhyzn5GcpBiAKY#8DXR1_Opi%1dqiaU0$EpZ^4`i*+<^A0_z(VT>4'
    'w2OWw6~ChQQdW)^weSjmff&*hu<BvbQYWfNz1x>acln)j+r{*)&+(o!FA=~b%@mhvQ;rM10pbOou(ujup0Fk6gwk`utI2-fz6oNc'
    ')-}bb27iuyYJ5BrVEM1>J9K5pE&7JxX8f7X175MAK=hJ7X^M~oC_0uDdozSfyM|%Zu8|YER}vU7FnIWc`gm-Rt6{R@D+oW2jE*F8'
    'jw^D>Lk7)TJLHu&f#Uim2!CLSnI{SesSzJlS&kHa&;8*lA%5^WTf5(Np9c=D)Fn|i!KEi<(=L76diid~jY`bRlfp*FWtqVjrUtw|'
    'O!Z0WP5e$_mX&*0i(;-2|9xFelOHg;;r-leswxJBdCF_+#jk4o>zgN7eXgE@y&HzaqX8k^6o*u^|B4)4^t_2<xw=S(;`mOKsKnZ4'
    ')vk5c{POXjo9z<4cD%xzm46bQFzFX5!z-fNQMKBDO}}VLUG8R!850`LF$M(NnEEP=SJ|n_j2}<g)s1nN5q5{S_b?ZNiI{Z*-{V;T'
    'X*1z<>LOWd8#F<jyHd`ED2eC-Q3ww+wt=b?TV+2|zo6F%ny))4Nwgsqd%AQX#!!vEY7Jbpfs}MMsOXhtT*5Wo@$U&ijWixt&f8co'
    'T|p!NM+^h&f>)8=IxS<}#$rp!Q(hO<L`e5PRv6A6(>G2gd~;cl9_&o0XG_I7?CK085Cl+MLyceLq_{oI{H;<bDsqZfw&hAAq<y3i'
    ';M<pM!9NL`((U9>2X{3-l)U>tkx6uR3iOBmQ~NotNr!MAd*aiEZCyf|UjZc&mD+9FtrqDD*1bZ=?h32#BN&$?FIw|9%V|Qexr3p!'
    '4(lFy3YwQJ@xR4f@hJ$ShABgB^Q7p$qgna&9ULTZgFwE|kg&xUM@OKAXq0R35m_`i<xrb#fWnA4ifmcew*e)@m<yt{y;iHiybjec'
    'n7t!A@H5@DsjEluP&0TSB?_<|`0<$$K=2|K!0ZKJRFCC;K(C05h9mlrSeqHhnyPoD$Qq*fG0e9XnMW`HA^ut(K`hV4_v~iZ*KMt1'
    'pA+AetON$a43J9QaZF`r-Ok=8ku*9{t0#R^th@^Qe(Xk}6Kqc5tB*PX;1wVyRZR^zRa-NM0`h;+pGQHaay*C3PJc*eN6V?m3A9H%'
    'NvEX*WqD*W1N9U;foC{wO&g*Zlu;qk6I?zR+K&F7o!X$<S)S=w)A+r}K-3rAZ2=%pZ$!yvU0<$;Ujh|$A3tY45OJbd^##ah={)14'
    ')ieg6FE?fNmXXO$_QNiB?;p%|LEM>YvSjmZy|CVHqvcgi_=3Ngr2+&Wiq;~18B^3;tO4}&9N46Ah1IoI=^32@o*@1ixdx0SG7M7<'
    '1(4Qv#_#@nwmvU<kXeCdnD3t{7--^yeFG?CxtV=su`jQoE4O5E9QOb7PYIhWmnK|coQkmzxyA`Lz$9-&%UiQbfreV_<aAn-w20Z1'
    'l$=C@9T_~eoXY5n%Z@)Ld&(|_<xIm6w@ZsLMo<gBm=FmqVV#sDSV2<dDEbEi)N;)2SK|7=6SD2mCty7YD%VVIXCW{{Ruiy=m*|it'
    '<Pc@jgBjce?Evcb{=|4`5f-qCt>(3>P~1{?W1Pow<8EkcC8t9uCXj3VU!NI1O5D#|b=p~k0$^&v+-$`N+-j*~bx(l>y*Fiyo$i>Q'
    'tae(lnv$N-5>-rA$-h>5D~d3p#li%X>4?!?X{MXt#K}VqT*F)ovI1B9tX&3Ys7w$JfT~`f(_~h`ug`E?{VN2>*Vp?4v5E$1&<vV@'
    '1J1Spa&1}xv!khfmJvI{16>2Wk_dfoBhDFEKEVep`z!<`Qm?bn9TE#o+yLy>g_t!3YH)bOB{YrR6OMIEMSxpb`%xdhiC;s;2b~1`'
    'drKlEaXOk6o{qN*!n$26Ii<|efSuIFrbHEnfqF*M9BsQ{?zoTn*!t(uEJ>*%k7*cR-bT`YDdkcQJtH`a>GlRAzx*E|VsbrvDGATr'
    'yXwVgZoY)|U5~lUP@L)3yOE+YD`%|32YWJNzk|bL9tu1UPN8`ALc$(t*P*Tw@~`oSdOg$?=N;#BpNTZ^;-I?@n{1`+E;Bv4Ack*v'
    'xS**LAQom~eEXU;J(c5{_kk(ZLsdW&&qqx`4O#Zjg@UKt?9B+g<K2DvRvzZ>YP1E@;fGS`NkNiXnvEFfex1&a==CjVsFE(S8IQ#T'
    'iWzUL+OR<5G4SO^OeesCiyOQpR)m))XUahlIe4>%)GxGKT)doC1E~XKe@}ZKz+zJA;~P^#11M=L5kG&b+f2fcZ@1zGKbd*k%D7!|'
    's^qQ^;jyFlaeU3IQy5%CdnN+IBZnl&-jcr(B{7Y}F%6HsXW^WWOMUy1-QIJ5hGLBB1oZEDJe;iFKw--Wf3qNljr8@rdv;VA?UIjO'
    ')$ZLU*w=vmuOmh*NEB6giS*@B98b_AHQZ#Y_&m^3g%oL(QHfu3JsST+284kBSLIcX;-z&4r2t4<cIt%Z%~)ufV1SBS4?dTZTx$<3'
    'f~jK4v-heN|E|c+i)hW;3Ey&Wq@V&gA?wi}Bo!*hG%7n*P(^GwO({09v|Q5pn?-1M3H0Gjn`%WYCjIVTJc)H4^JU=2C86Y)%6Gz$'
    'X4;~g()Fv#je*b#PEr^&6h#gxY6>t32*)ttXXEFmJ$8;^Pnwb)q$jQ70_Iq{2p<gp1%12UgN2px0Nya^Bvf`8tj(CLgo?#alqT0U'
    'IqRz|$p=MVMt#abWsE@+hhk1Gh8aK!nA+bQG&3VUSG{e|5s&{W9&u!PpPkcBCvPOfM|%O%rviOBSK~}xb-BPk2$k@;?Zp~e)tEUq'
    'na;&Fs2^p%+G9=hDyI=aX+VTSDo`6WF2$8~6bCgaA1*1@J7W*et35q~fS!a+O+^Wi0zW9$&fsS$S&*@bis02NTh6&Unl6;~u%iRJ'
    '0}&-mYcR2#%VhS;eP&jzz1WL(Sum=Og#+gj6JtEGQ`FWiv^57~v>U2?aJRC5k1V*YUce?hXe@xvmiWX1i(KXrw}?mWA?%0Tw`Xzm'
    'M-;4)vXv<=P$d7V?PGNX{^8NA)Z~1Dis4{j`RDg^e4MM+JAEOze9G1hm)~dnMcsE*=0xSKR{ZRdPNTs;qkz?If1(%$sCOcxF%KW$'
    'F}HdG22R|lx7tb$R*COE0~FjkU$0o-Qnndt;q*f<wfTLGy;%dg%0_4IoAT~zt9i6G@o}z(`~y^lQsL!D^&VmXZNba|3cPpu&S?n>'
    '{+_GZCq}2=yy!sdxG&|@U1mH-KOPvn|HY~&2{eY|fIKFh4-J77We2~A>;bNkB;9%1eSp*V7jkbV$wiEVQgys`I%>w115KQa`?$0f'
    'J|#wBKWu>LsNV$N9o;W@^~r@Lax7XO=QRk2si>QL-{x!eiLXj!;mxHDOF_r)5RFu+n>=}@w<WJPP^W*KGP~*d3Ag$fF11{27VcN>'
    'S42i~4MKP={orL%L4#=ZmB^-heRNdyJBB3Af&_xwPy%%F+e^`V6JWlt4=@bros)X%E9B7!l>1+qBzTywZg&}N@W-Bs`PGQ*4;Rn!'
    '@fRfm)@_4fk2WqqTu-zg&<e7q>*KM0r>9=(pRJjJyi^rMvY3=g|ARl2A1yFESr^d*4&<`i)^XVpYMBILX<f5G<bgl<r1sRz^%msv'
    'u@Hky64lA_Z46FuD}@Wu7laj&BuP&e6O16ev~QNcHp_!{!;(MlpV^kfmGDK0Mv*4LOkFUvuvmEQei7i<yJ?c(^Y-uM3|yqv_OrYp'
    '11P6#@W^|Z8gi-X@E_m>n(upb8Qu6<?<x<9SWYN8Q^m>d*==CmNB?4lo@Wt(+}rK%h6!J?Nq5d&&*g#OSW>K*9_$$CTUAb7<I|4a'
    's34ZpJpslB?%AR6>DB8g(6KBGHpW1Db1{<54}U$N*mj+BCe8G9qIM-<GlVo?GF55>eD&gEy7N2u&-mr;ehyxNZDuCm1L|LCRT}1S'
    '9f^r#_YhJa@_`C02-v(6jT&+BAfC{Dz4Dnn4z+RcLE8kUEG6da`#~S`j9O+UF!%#PK6{AR2LC^My$mY~-Pipxo$M*rmlW%kcuBI<'
    'W2^ddDy%jDC=1Zk$+ob06?;y|9^O2z>)lAv`+{oKtMA5yc9K3dl_+ZC+lf{(JFxt$x*FI&uVi6uHHyiQ>x7^Rc^qZMR`f~PxeQnC'
    'Ue)BrcdXCG&HlrI3i82&9+UIJZf#=NR+Tuy?+Qw=u18NFyJLT6e#LM1yP2gHKYW_-Fou>3Jr>bi(H;a<g6OCTWDE>}OU;pw&BzQ|'
    '&D#Sk*StqA^0EcQhOz;C!1>`j7}kTSaOl&gu1{1B&s;(Jn_j>FGdZ<q<_(q+tlS0-c6n2<?#3zw9%x#2keseJQn~SPeIUJ?gL`$2'
    's-;2H0o_0jtkryV)wWwk3cI2`P<VQfQlme468&^7OWEOOGdLTKAv$r4+X45y0VY-F#T(8%zfD$70GCXc_yM3lCo$gs?xky}lI`%C'
    '=$gy{4x#l~=Xt0_9BBlJg4XyhXkhNNO^5FY6`LwteVP;sr<hhPQ>_+ihzQxQ9p!5Y$<U&jW5E&<mV&$!-zzF4fJVMcP@YxiK<UCF'
    'VBQP!Nmceav9veE$Ub_=_V3!AC9nBh^UWZ+KNzm36gcgNNsS<5?A88pJ!eKG(d&V!k|8O(1iH3t$c<Y`RBloxhV@{pwKK_eCG@kA'
    '%hj#vj$bHA4PraXucCy8&}2T@@T5OFvQ@N0uc$wODy8?PIx{mUP#E}y>bYm^RU_kLhTR>r&)~2Pq?XpLrGb$I3P1`6pM+6ae!IF?'
    'pWk?2nw1w#?1JwCr~oJMrwVUvVUEX2!pyyW9zER<1ee(syxW=>xvu5uocZM+D`V{@aUvPvrHu_W(xs+V27amF8jAMFir)rf;FC^#'
    'KW%o!0?McGu=DeJa=icV?U9Z{!b$&60x6mK@4za9elr#Z!G<C!GqPIUTs~ttYcsuCQ%%3$_tocHKO&G`X7i&jYt9sYCj~uiNuNN#'
    'g6C-Zs0}zGq@&O~AVId`^yvnsQwm8Tlaa|vdmyKpK;O9k-}W5JG)K~<8~hqjtPgQ$hL23ZH+0s3Z+b)Q#h}`$1=0zw4IMtYO#ZJ5'
    '!A(juFYzm$JgO33odPojpgG2Wz$^NFqYNkQG5L%2#9M@%pmU*+D$mD-yEaqA^HiSrNDhDVvd2>M;2R;y(o;Nx60@7}cN5be=u2A9'
    'oj0$%)Qd!X1up_41?faW8Qk~Ao0|XhAuKyVcR0!7iD}YhC#ggcMuunyu9%9ChIeFveLAn_%;#Im7h{O1zw|7b<3l*of*8?{DX>xG'
    's5X9fD2>C}HXEdW5Z3gX!X7MN`DozmS>3t~;MyICV_NI6q{N|=g~_b6%-e0V9{-eQC;bDvl<3Ax_$e5&bU#I0tw-e(L#dacQg6ht'
    'mA3vm)W~*p6pMLrH}hA#l{vy3_0P%7Zolg8(=J?f0N=@tV+u0Fz|s_)0>Mz&CD!P{tC5r$sOHSC@ti!`<J;kI5$9J~J+6mJ&eVrO'
    '7y0=58yYY(%taqO^lX)XrC=Oq(^i6I)>3Ah3epI$Ms$}qeoQDG%kZMM<CE0Yl>G9KC;gP8j3D%ie|l$JxrXI<p<`H^)9TG}+b&f%'
    'z)<WD*%*m@qm})MC1~kB88l3+@bhq@|9i{b+J(*lr_Z4mrz7Tgpk`GKx5SJmy;{m15>?04c&Ku}lJYi!qN`nJg;5%vXBp3)?E{_3'
    'Y#8nd0x|#__|@J~EFe0lYF@C^OLXAMpX@5p5W>Xw+`rUQ)V`pt8tThCat|VcF1agO%}tu9K&FGiG+7B^FdRYs&5pc=c2BgkLCSpo'
    'H2vnCe|<enYM|>ltkmaA)lc{jq9c%@2Ix$nKa6iXHw>)_UUc&%g{h+crR$q~68*+%QWw&7;S)7s4J{pa<ORCBJZH^%7*KFtPZ>mQ'
    'gJGDUX^!tHrN7`{+nj)d+0VrzMh6rFdM0^vVq5&PbZv})8&(b^iUTAmq2`LP<uAXgJO%b1g;DFk+Z8(Xb?De0!8n&rHWcA31In$y'
    '+~hhd2&pee7z#&pn)a@Y?h9Sw;;2Fp+Kw1`rEVnZ!;0+qw1<<Q$7Bz1dNuW9dlnY<pNRGCkIu|HEn^e<J5mPIlzYlwVgN~5z8KmZ'
    'Lm0rWWphtXi{aI_G3b_n<JM~F^jKhrJ>;66+x4dS6kPGCf~uvuz>ChaJA)zPzOjTBx(FqhIM903($-hhkkgMx@fM@MHQq&v*~@l3'
    'c8fPJASxGk_OwZlER@gB^xb#JLrMhJER$=oz6&lW2`W*CeJ%V%UmpY@A45q#HXiLZ?`jU0Iru2~@g9CJ(Zn;odLrQ14xAG(oE5#R'
    'PKp3*#g<(M8TQPaYr<(#w@*wNK`fbCa*$uAp?3I~fwKKj-9JS}vQ!d06TY|XfkJ+iCt}FfYhjtDyL?>#hi1RqM`0%~=Eee?hNLR;'
    's7_YEwLdJS6+u2f0e=VuNHVa&q(Fo<viu3itP-zwi5m!C>*ouu=e>#&a>jWB*HTEpb7p5s6Ecjr4XFrTh7Nj`E_E8Rb;AiNJL=k+'
    '6#~2jjMYsM>@6_k4eT26E?-#iHEM2qz>RuJCp!mA-(1Y8&L2G2@+?lhRNSfk7gP&wNGzzR5DXo(uJ`nD(B&(Hc5fY;+6<59?oUf!'
    '<rhk~YA6V@v?USxQ70HUVW{Wj_hqDI3yk{hjSN04jPAB*z;Df;5^Vi};47qN&|cK_{S~yU_)tREjBvBykTg&EYsha?$hZptSR_ae'
    'r;g<T0`F|lyqo1*1`3)GWt1B>^l|udHtAs+?8p`D%Xu!(sd2A%dMSoBGA_Bv<<QDjjXjBXCutXFPWmbylEZEwNvQ04e%kDd(8#{R'
    '2^1@!sfvb0Z4BEPj$2>;f<B=(LUE7A*GWA$&9pq~U(h(s14hV$oSvcLKCECuhlW4~uptjBL0)M`LgkhtDQfcpIrK88?3z$li7u`H'
    'eeI&7A>6YwYb!55p?}8%G3hCp3{LNBCEOw0Wtk#hpP<FCYRy`5x7t;V*ZD!Kx&7hmW0bzs=;P11-;MOLe=YjizDLdzNZP|LH)#s%'
    'bfJW(TzH?r4Z#bY0L+|$BhqktLwFmgZt~dfd0Zrp5l2$fepSU-8TYfaK)C}<A6=}3<G*J<d<3MqL>eA(Z&MTb8PFhmNXp{HD86EO'
    '!0^Id0>jpvXYYlsN`HLZg67*rtGq-v6qhMzw@Ne=P!7UFfbf(EkGVi{>+6h#c}%B3*r;LEj4%S*<KA5=#ym_4`g!p6|5)dwiDflX'
    'yRdbN?=(q%mIyEh;AbWc`?`-7<yNrzi3KY{@e-cf2$KkyQ$bcnXqUAZT_ra(d)(934d7KzdV?jsz$GJV7fG_%zCE*(2EC4xhv@|X'
    'kv+7av)<rCPOs%UAT)qcm~i=V#r53E52$`o+JpA=`jhGUGOXs4+Sj{cKx<@HM{&MYztNNycpK1sVe<g;iU{L=U|6&T{QZZBz<x@n'
    '{g-XM&KlaQc>1yv-Sb@On2wRjug()<IpWK8SNe92=>gc%6sMVZ=mw0#Z`f%@KD`7u?_Isb0<-nH+sf;noa?@?vsf5%XDpFa2obI}'
    '#e<y69av81-w)kXO~$usL`yj2sXvMk%7B!DC>-ejzeUwRfnQ1zlD$bdI3TW8B)l^b>r6L>`KVVPKbKdyqZ|-b6%zuqes4dOFhvXn'
    'xPBaby=9A|z-4tG>dpUzPgn_zTj0iWtxNAE_vfUr58^@fWsj)W=)AJQ1RTxuKtSXJ{5-Fea|LP<*tv`6<P<Y~K5dVUxCJ&1F&!S8'
    'G*mb~Msf7aGmlC5=6uDi&<1XJmWS(|9XkN0pKw<eRm3Y|vanSa*!0X5wUfa<y4ilT{8^|rw~AR0(@A^}Fk`rzGu#4O<YmOb%+6_B'
    'EgkA4AI(O|U~NP)6?8!x5~>R>!g;wySQ@^2!`3SHp(mk&-dS&!Py|dQVsy`H8}Nfg-3^OQdr!%Gg!wv@uhQ+WGF@IZhDC>O!-;Ol'
    '@6W-lp;Us(*Q}gq;Y@?cj<dwc4w4S1)}PzZxKC1!U^~DucakQZUFFPpNL`O1at37{A?+FIFI8rsDC2A*<<sN8n2GK_MjWS;KVS?p'
    'un3{ROQQNc_6ba{^RTqSBlJlZ0xjeowW=F?KTJ!GV~~U7K+_wU0%(^B4Y_l$f&YJ>4Vbyia@Oxlr~(x6G7~wDf`UtWN2c3@Qz#L('
    'F|4{U5dY}!i$(-1okEvrDggJx@m=p`Gr%@)33Qa5QI2iXLXWDswOtghOB2mx$VmT^C!o}tm5&BcfLPL}7n2-|jQ?1FhUy1h1_u->'
    'BJ_5cO{G0VXUOV=L^jMPPPAfFQmo!(V43kb51~F7C~SK};gw4w&$$4V#ZU5tDIcd81qwd35@n_buQU_>A^6D;*BgNUHQMPlxA4+4'
    '?XVk}oV7B$SKa|;I<-x&d(D1*EGrTS&*uWM&f%)0+<eK(H1b>mazFyxnAe4<?$rQtQ0GF9AK9yf{AMu+5=k11u&V!~0!fX~KYq*U'
    '9wMkA|8i<>MtQuU@K4-!-w!v=-ES^-b4vaex1jm=IS(AQo>u89C<$DUc5xq3yDV%q-=Aw1g#l~5MN@fJ9;TU2?Udrm*#cj1KH6l<'
    'T^@qp^e5H$!DiS2R)A75O~}_=cN$m_yrRCa0r3E0HP>sjVQP;#^lQ1y__c;}o6HJ`Z}w)uD`{3IP~4=%M&dsnQ85Zuo??TNsMz;7'
    '901YDH$uQ&IZRf~>s(gFvZ)w|-Pga<wypeW1G!RE(JrJQI@(6zU|Z;9-*wvJHL2<{azA}CZC;SlVpQi=S{K{wI)Cm18-h}BmxJ3@'
    'ZTe*uN5e5wF8%WAnU~p0G~_V8nkIX01V7zn{&T^*(T1IG0C-ep$`X0>LLKZQGt-)4V{ox&lx&)UXWzY3d!TmK18W(-RV}cWW?S`x'
    'tN%3=FFYXeV7HwLfU8%(>bDWwb)0O5bWS(L??SU=Amt*-R5923479yzjo4pBp1wKh*CO4kgHyD3CXx(<7^r%uN}Ia?Y<XC))Ek+x'
    '1dy0iWFQoNSSSpuCII-5Asr#-VMos)>;Q<R(*y-SRjGzq;g#;c!wGW0JKrFl-i*anDCf2gZPjth(>p;sWurrT2OC23vVAA7g0Xg<'
    'W}pyq$%;|#|8Fq$PFoN0<oCdbp!h6>GG9kEVTt0cSoCN&EOy+6KK?fFQygWyNB`gbp+kz@p`F-NUZAXEIjQbuV^<%+YQGbr|D&q('
    '2}v!;<PZI}!SPqgsX|@+O2CzRvu#c|ul#T1S7H6%0_kOsHpLVkvqkNkczmX#hcV!K7`HSfFPepRf`^;|fF5gr2)O@}umlk&P(xmg'
    'w2^QiFg%3=&zS!2p55fg;Lnd6Uea^RyS+9~!wElgVdgt&*^&i1wKN-S`u}wsnY&*szL?Pi{QMgweL3%qk#5T9KH(o_Xt(6~Xxs^0'
    'Q4FUHy>-%qN#b+EuGf%dZUCQ<vC_Daxr06|nWJ4pIT5PShqIxLaz_J&*vd%EtzLMNdw-}vKs1DW=?_It4#V#C2RXp`O#)QNg<dSl'
    'n41kscL^^uPPJBuiGEBGX6)}(^&_?6X>oN5){mb?-q4)ESn@J$mPg5Y(Mi9wJ<~J0018|x$Xfc<noA3n<<XO_CQF+i)78@#B+vOt'
    'C7H^QeA1i3yRg(vs#qh9$W;5g?1snp)*SR#NmWdVg#f{><PI^2wHtTye6W9cW~D^ew#CH*tg$;-S|5I41}jk>tiYzvt+vBU>0l1%'
    '-A8$tJMz}`vAX{e^}`p3s}EKbe^jg$z9OmR;>P)3S8mIXPLyf=M+@{kj?b{pLQ0+Lz)No?Q#zTB1i#MY<>)O$!yjk34Ws=s3@HK;'
    'B(Hzl_$xBIZq<j_5fpIfOm-Vb{|jNYFCBQ%7qwa|F#7eFI3~@knMWpOGGeLy(N|miO9{~4s%&M;i|{|GQ5v$cs$s>Bt|{Usq24xE'
    '(b&d1BkU5hbi;SdvM_b_@_7p)o^$gPlgsC-2RpVhq}*AM2jNTV^zdl^l2_rKGDAbA-7N$gre+5*f~5EWPx*Ozt0shV>9Cr8xFSVH'
    'mmYL4MeX>p^~*c11)S!IkcIQ*lDF4e9VMfX@@^{4Rq^IIiT-otFu}^w-4ck*__BqcetWes?cI1}IRB5^`Rs?60mVe+S@I@k$9i8-'
    'cVFy^FT#i^VCkbm=X6<u{f=y|!+5N#qdAE9fKUX;=1e?9V?=4N1Cz$(uy~x>DX3Nw5CsNUN=bhCX7*&p-dJV2RaVVr4%Duw&kWM+'
    'tK-7s%z~yf2+%W$8k#`LPpwEU5v+FR^lD&;ZN@s2*3A2peA1w0h-@m0F?31x#lk|SaK2E*vr2yi@VjJn+(xtZMSVbfrV<<EV(1*~'
    'eAQN-rh7MzX_xVG3P&LG!uw>d5Eudsxj#~g%7O4-Tj_SH{=n)asuJP%o#3bj)blLTK?C#xtX3D}yAyC(Av0g*rvmu_0M7(6=};dy'
    'QK*Kd`_qtZZ!a>h8Du%ie)N|MDFI+_XCyvWOr!#!F*h8t*9H6_$Oq5-Nt*Js$T>*U3HvYDzAPVgL)T@7*zj`khl>TbFGD{QP-BN`'
    'bWeBBOCR-ML@UA+<LE8;J@j4}qlW(QpHqDuu5%R~nJ`JTqJ{4Sni&;Ugd5{}dl}wU3nbf{3;I)uJ4)fK%WxHLJgW78{6y;`l3Ru%'
    ';BR}jADYahuLmOi{Vk$t(Jn%Z8S@o~#EuK2xydEg{#fr_2ry|h$n9E!ik{F7_7orxWI(}!MhN#~C*W#TJ%;PzJ5dy}hXDl>VPf%a'
    'P^RTb1ad3|C!5<MUWn0EXzJih*PD^_GPGqK>;g>QwElzt=gS?k{Q*)Mjp98jy1p&1(RAzgn#<P0j%N5rrg@V)@@AtT`#o;d>8R0|'
    'U;kPo>XYau)woTe3wx3ZsLky@$9L}>wjz3&gbrM6(G^j<CY^eVO!{h)yIH5$#gfVxtCOd<7wWlG6Vf^dt6|AZE3Al=j-Nu-^2OQL'
    '>FOD|N47hyhCY^zO+Dm_g~|W{5%_M#QYi8y1{0P(TY+QI?qxmCtV2<+pF9Ybcg7Fmc!HOq={WQnhNu<S4vQ=rElWcXxqryv|2pNm'
    'sJkw=>4>j|q=TAjt+^pS@mhfM+=h3MGB1sEokl2?Zi**TnRE1;bXjN>33dAKDC1eMADA^eG#Y9Q0Vltgo@H6!X_baQVvt;s#$;~n'
    ')_H{C1Sin)VXy9eg7IkMU07VFnFhuf49%+3<?EtDt=Ju{!?IU8TtydZ$}8)f;NbhDmGpmf9k4o%6tDUBwt^U_ZX=YB+V|r@CCYQ~'
    '|F^-%t*=x7oj{q{(x%roL=M6ZW$Xh@W=U}NZp{d5zB?jI)89IYQ}p{|o3Akixn_c(;fOT48Gz(5p>LR4%7K8txE9pIp-YY{;_mm3'
    'F7R{@SXNJ2iH1U%cM9TP2#GImiRu7V45mdOg6XP2>dM1YlYF#2fNw$+*jlvzh&7pdIm3!<*0DI1T!A~yzJ*KNHocNJ^)yW-iz9Wi'
    'P+jNQwGZrgA58r<$z?L88F3qj8Oiw@UY1KyBRy@55MJFPaJQDEP!~r#gxZ~zSnrIthnQhdRNV|?)~yu>a6#0U1uV<>kP;`yEhO%7'
    ')ZbuL<`5~M#mZn5`T9H^`^~HfVLn~WYSI!sXXX<eoAfpC^A(zkI>?r&aFBP;cKi5pjj}I6m7uz6FTcHY;R0dv{k8a2j&4;+6Nr~='
    'v4ZqI+5^sH*&;Ut90mc_K^lsFZt&)`f1quCba{pdtg6GCh=<cui~SeNJslRCHMxyEnDksbHE;?O<7ja%Y8A8Qu<H5&V6^cqO0B#}'
    'JT=N@a<*)R+3-nA3+S3IlsKA3gc*{BTnHjPnl;3sqy<+Ud;iL6g`KNQLU!|xwdQZ1V*)Jc#dO6zSJmf&LyNfDo;kG0IQ`!r3UoGM'
    '_4q!Gf@v$pqE<`1&5KCd=Yp?f5I;XObmCMyJ5uix*E{u>57Sh3oK86zamA=+o+Y4YLDyY-oGF}W)0Vg-hCmp<(&vDi;wvPao#x){'
    'e^1|m3z}`f&zo5pD?#%p*m?78bVl`)!)Egoysd{yb{iZ_e`t`RQljSrv%@&qZY4S&Pge5PX;a$AgG_o~Qg)Hokl3h?``fMY3VMS+'
    '1haVUUGfIY@;6cqaboRF4W{K#Jb*7JNF)>#Jp%Jx`McIb2SUk$&9H{*N>eTW9qy+$v}VX7IyTe!@PsJG)m51nQVF?q?uLS^qyS)W'
    'nRjMid6wBMjkF=XXeX;dGw>K&5kMgG6<;&OKO@PEJjMX>X8PJ_OP~)XoFoY*RyPZY@5m-RrVnNg=_h?oWv(g74rnKKX(8z->$mYC'
    '2AtcDZ;23T?y(OUmCmrSVTg)i<*Sc7MU3RtN`U}+)86pcbA9l&hWtmGk;~j}B%HZgJ|Kqayk{NnTMzfYSb%BGtHw#?l5-rI3Mk&;'
    '3Pf=lU&rVCV&cq2O4*e|YHVDOZtjIJ4*kyi!m+oaD|c-|q27UJ<5fW!iXwmTE*_8zbfPHx3F4<R8b~u5KGhc{!W%h)ddhfxm>#gv'
    'xQMs^Y1Xp)3(uz;A30=xCY9C7k`3wD`Ru2<f+?XZaX<ETKsRo|M-?Zb=_8w1YVH%*`<3Y7>6d`g)Ade4N&S0Pc;Z&y!0~bEnU)pl'
    'dRYSa;K(58O3&`8FmHH2$mM5)D06d&T54^EM6g-Q`*)=h3Z?8a>Ba<>rzt`!Yz%8;Hgt6&ub_wf(6j4q1L0e4$F<_}B1DwKjB)x!'
    'f{b0Cbp!2$Z#86=Vt2Xl7>acdY`35c7kPktB*I#o4RJDdJY7+hYCW(jAeWK$w+O%wDr)vv;HZH&+Dj_>p6Vyl@G_CQD1PLO2CqyW'
    'HXx2YkpR<WlJcNrIQE%<lava^utd{S7b8+oL!x6A%jP@%)m%W1MdA%X*f}J75I7f<|Ey>$a&-!#9!8!7rHV_f())!o*g7PWbIrK%'
    'WcZLFCQSg=&QI?TeiNQcmV4yl{mH`gr)FO$I3OC3)`@==yXGr|TY9uhcH3K^^a2nB2oh?(Tf-|y44&sG$&4LVI0ALcvGNoa@#9dA'
    'GX&;f^XdR{PahKLEhK#h2+PWLu`q%1x9LkxNXX3|%tC=?Y9V+-viTAAg<nYmpCSRQkL14zF>tM`dhZ_@7RRGCoGWyxIhTiR58p0D'
    'rOdd4?3zG%DI5%6$SC5ur2oiJW{}&qNNLgF&$^4j_vS$R2R*Nlf|ir4LADWRFV^-ne0OxD9(k*b1W`HoA3j(Na+TbvjpnpPecr#u'
    'G9N4kpA|LTO_yg;K&xHTuT54E4K65r?iOo#{`mK9qOc)tobCy?uhs(P1N4<md;k)Cm`lIPVKxQnl%4;kxOaH!Q?64%$Tl3*<4g>I'
    '|8ulUuTNN8&{%w4-*J7zMzdM}2y<;Mj9tPPi|;^vH4xrGGUPmZxLF((jBAs>7+%scyZTbIU4iXIJHvUl2r03@6mFKyGbNw2Ic<8!'
    '&OT94l8w(1G`RN|x=m4M`MI&rC+`6z5gUb?LdrveUnhbaU~4xhoZ=hIRfy4g1YpWZjl5U@Ui4}r<0Wsb#2s(Q>g+4X+HwXF+}E#p'
    'm%iDPctzcMHHB}^p1|MDFQ(8_*F!7v8k;-hG)&r7`$>^nxI#NaE&bNd^S#!vsLS&G`9gafns-E53C|W<4CWhki_)9}JgT{{i$Ay4'
    'C8MaB5k$_sWyaj?Nx=D}@HfJ>WRY46{b3XKm2&!w_Raxa&*qO|;~f}m3L`+*3M@hdyB<l;`q+*X?mfyhF&;a}DL4aflphIaCZj8m'
    'YQ;d(9&{@$eK=*LO(8e+k(mBa#hI^}3IbzC;+iFlX{ux$ufW1Gf9K(^S}`}mqy23X7Nb_V(0aDJ$3Ye{0Be{_t<xNI#y^`Q-IJ=3'
    'r;{@A{vRxZu2V4o;WvKY(@W2<ft%)zruzNcgtt(!9Qb%O%LI+bR1gq<VF>IjMTb+IZ~kl7oQ8ilQ$@D8Dr5?(HNQ;Yv>aO>e}Y2r'
    'sr}uDe!SZqKc1a-!lr0reQ7I<t7(4&(nC~{pwtu*e!A2mK#nbv!TU^6@VsGOlNrKg;<qrWja>kCXj&!+*lC-Xb%-*1)QQS-<4Sjs'
    'Fb!_vr!OqbFH}v)Z1Lv+S{0Fd+g;G;F(D<_2<IW87g{c*!n<r;tPl+{tH~IfvTzCM8^SE_AFq3o$&}-r+;MxsBHU>{zKbW?u*w$l'
    '?QMgW81yO(97(td5F`Lg;I}Ifxv6v|y>(bJ$~MNpc{MH#xJcK%iN&rb(~tiztK!4Tb<OlzwVzu?fw=WKn8MaC;9&MW{fbrOA13Yd'
    '-u(JbF9^5iJv=cv-A;a#U$i5rO!uS~GKB!z(PMafCy^4|k`^eJ!G0V^PaA?k89*@Ap%Ocp#Hk)i^UL#p7f<RG26+}5k;Uz&Pa#f0'
    '#+&>z@;(4sp*N*I$0BpvzQPV=2^0a(?}jH8Gg_%}+J)XNwS|-a1ToW{fK7JW1A`=U&sWcf;Ve6JTvx^xw@lki3!18STajU-OW!<e'
    'g^vse-s$hr>8<W|(ShYAt~ba<RWmFWD^vet8orjqb&#moAT`yVI0H2rqBI_np#NRsyz<;97ncW{_?3;-kmNmjjF8xKCs^EkbKTA?'
    'zG{$%o4@iGel>F%fO?7?F{Hx~H=SU1=Ut$kIt~Ghaa~uJV?@ATZT!#(kAsCzy}`2qo@eyAou@dXYQ!3#!plB_Sc4N8g#~qhDZ`3?'
    'poz}_&KANfczySg&Za-K1Qfd31)*_VoZJk)_0}gAeFrTy(kAzjBHFA8swWl^<b#odqWYeG&8X@HMb-vE|6W>?1}d;{acX|-;eT?$'
    '5M8`u?aNm<mSh6t6)zhOFj!a2Y`VKL0+u|ACT&knN$&bT;;iImaG2AWO&nSnAtD{3Daei$XNR4)BDW&H?Qe&=r?*{u;5%oyo{^Pf'
    'avb^7xVgy}(_LUYYV@^L4}L^jrB*=p^Gf{Em5NBPSC3dW=zTsH34G+>33prPa%!gqf@;*XHp>86&`mJyXVp~OkgWY~4&mMQu%D6n'
    '!!}cN$aLH7)CbK63DZg#o6Q>iAnQgP`06h1loTiS+?;xAsJ(-uG&C#<2SV^qw;!sbjBYDqZK^*pn=8i6P3y4>>zZ-H`e@_TlG5d1'
    '`M_Z0m0}D&nIwRzm(Q73LbBI$EpvOr<Y{fB0ktD$7Ro}5EUk5<sFdLj3aHpv|Ge1cQ1((P*aye%;WF)PRL)@_5RYEIYm4Y_<M)jC'
    'acjC3N=*A9uleN&@k7!A;g4zI!;t(l{4N9Zoyps)C8`xvAR(6Gme4aUl^fIhRB^mim5&!m1gj#^+@yrz%V#IAWhDE&z<{~-JiR6B'
    '%YinLT*~VoVDPTnYbsi@VyfWjY2q#iKgzK-74#B&mgQB~MQd>vfV*_MtT5&)tDB|FpOWw{Y`vR|M6%g`#Y`t*r{^p5lfJHjzYQJy'
    '(oQf=32^;VyimLiiy;Ci>F}w}4Q{Ghe;(<Vmgp9TWp-Iy^<Xbi0vmU2Ne{g@Dl$TVk4V9mZf5QdcTD9qs-|z=|Dpse7-+J=Ky%n!'
    'q1ZZ%N{XAsob6*sJfO{0Ay!jb(Dq?GQ_O}MPSOs+5fYMlT1k`fD?Gqx?pQ)#z_ZY?Y-M#x4aMaH8D+8bG!TlrcZ@G)O-fzTMo!N#'
    '6$gEsU(yia*NjooIMgYoP!G-09Joz+NutHAis&@18sqZbk@+WL9e0<+4^$Y@gdoqBlRI3FVu1k?TU)!xAvS-eewD5e96JZsg#L!i'
    'v7~7k_mO)mWk7a=F1oWw9l<g^G#>WZtSL&Dyn&V1W8XW|J{>>xY7peVGOw~Roclu1)<uBlU~QAhC-o=EoeE5$koU1~7Ddv?b1-l@'
    '3(Kf@82T%@{Ckt(G(Y76*L~e|p<6?gaSgeQNNYX@_0R`9NE*D2aIjZD<Q7v9p)7$RL$NhY6Hy8d$(SXXXpm}W3JWU)Y4N}2Y}(NL'
    ';r<yk-x3Z$Raustsz!4!rM^w6Y1-H3N=$gFui9b6Q5f%z&FWOLUDBOvOp@xady9F}8QR5UQ-g{96#9o_Z-VaH++-Z3=`J+ML-?$b'
    'V1FI#ie3#NCot$zaX%%bPb#*)4?2bRoP~{RJ=0yni8)QZRA$b-<A}ocI|QY)fceQetJ$3|#PSxQ!u>299CqiMz{F<<459noUoHT#'
    '5uz854+bM;g?tOo_}sg~hhlbBj>K6ENU^(X!N*@a+wHxU?`gLUsOTcV;-xFqZJ@l{yS#lVT9%HisDR3DqM}}O%xS<vYojwe>rJ2L'
    'X=eRo{rtyaMiq(<-(cUcH!z2<02_e+;z<m3LtA406r5A1FVWo}J8C|oKR?{#iN?#dSc6r~w#}XkhwpO;aK+1SFbwywm^SIcBvCoD'
    'KKGh%z#GvxF1%2lMN1AkXa;y8BYV|A=P{fbNav}}t8uqR!hLy$c<KT(A&T^3rpS9axfLx;DWEs?khJ@{C3enm@}A$^dLCDe20}D>'
    'p<@fLvhfnG@P<dAXvtBk3H+sEOOtxq4WYR$VVi2@C}Z_YyM~men}YW7i_68yZv=M*+MWukn9U8kWpPowlY)W;_ZMxGZyKSvh<vK<'
    'X_)d``f9es96j9y;Dh}3H4T2hVk+)p{}RjmYhjdA*J5h<xq8aZBp5s@JWr!nwDwuJ44UF56IDE|lXhCbtmlDiQjugqY=*^Z9_mtp'
    'c;_374%1Nk=(ocJL3rnG$P>=x=qiuKsM*6CL2jGq6_DH2T`2S8D$uZ|r~!R&6NLItsh4|6J%nb3vyho+_Li|gwEHh~$xRN*9D|9A'
    '{t<P?RM~*t<ARJxN=^q=*E#DKgZINKAz<wMo>2v$_#^M3czi|=S6rn9J}vU6ZnoqnS7?H?@zqSk{Rt4b(-H~7py$3~CS8-f@q~!j'
    '1NeB~kOZZ=SvC>xFftCJzHAX<=X=Op_-m)AG+M(leX;dCYIdCD#yV#ne)=kHT951jX^tCA=xp%@D)kq}zWUQ7Rq@_L=p_esoWPv4'
    'LFZ+yI9jNLQ%Zi-l+0GD<}gXYMvxb%udP?4rL^7BQ@W)N5(@SU)e{fc9KdXd+Un;R(=h(Ow~0s{BZdh0l~9h!Pm@UDJMO0bLxv_Q'
    'e0#BM871DCdkkF^bwkC<)?$zs5w||8Mv@~nNPGD1TGQT)6sJk!E=DMmajJHT3>huy$2j1t=&`;IX~uQg@a(FzwZ0@8SwC3S3eVZs'
    's31yf82u`6IgS|Z6ikQO3~Adi=cijGfoF{wieR+JpRFU`W&zUl^m@LBgb-rp!vO<_L@p!L-Uxf8(8oEx?clK7<SRmjKNgjl%JUn('
    'g<iqoLs%mxXsY3!<@gLH9l*+1>xU$jFB5+_vb-S=(DM%v;=>T~G|qh7o;+CTX{$Bp$CmHf^LUdJyOXRR3>pTp<ks1)me9`2$2rcK'
    'vYn7@0EMsl^^D`a2=*<LIeC&xJV5}5{4gm+g1U%lYI^73<A!2UFJlBxoU&~&^f_`oGq8}cx>=S1yFHP9SR$L2!5(9v5KX)dSyTX-'
    'k4>7nR(MkJgQk~&L5x79*eGx@lEw2k48rN*alDFYjUkez&s89X3{o@tIcuHR-ytu^58h0e;W4|Mx)bgvVmJ+OM10v8TWKC%1X8yh'
    'BK{UI4U(0Mr2M)sp5}(4_bcKFhXK9yG;kl#%9O~cB}XgB_5R=py)#6h|9X1+k_Xo7K<I$=L$)W6xyJ(ymqy@|%}X~a%P}N3j>?@n'
    'GQIg}xt0j2ybTqhVvxz4v?yQ!YPS=xTd7Z#sWikCilO0NG3rp#fCbhAct4WRu$RhZwJ+oRItfz<G)y<s^Y*>Uu{Q|j6<<^5uc`(m'
    'dr>ELK^2tOw)I!)JbHRqA>!A#YY^F6N2|lD)O$VrTXOIOgkridI~Ir0+jZ2y+ZgdsvP%8xq`;o%;Rb0C!;$0^nfKm3oox=p+Lf^D'
    'W)_i`)&qVMw*|(^{@AVCpAep$nRh$Ona)oRXIU)BR<1uqQ(<Q$iF#*-GWjHStM`EZ=P<9jHRF+ynp5w!M$)v({!E-O&)M<qiO;|K'
    '_u7LB8n*gL-n-(tu2c>q!oB&Hv-ID-y-qr0I;J~Ap`AH_&lT;_V`oN`1-Bt&MK(tcx@Y(!;BX&jyuf90u`tM=z><tSou5ChsZkb9'
    'S=>LHlfm&hJ?wrU>7l>Kh|=0a*#fl#+U3S34Q@U--8`u}C_%7H2Dz}Ja3@Z4{9sq0XB<Jg;LT2Vc8@mbRcm?G?2j(R-!huCco#Xn'
    'F(ZKzo+N#zD)|_Aq*?8aK@(^v5Zuj4OR84vv7qpuxu<Itq=OUxJ~_Dw$#0&dlQpUXsg5c=2NKlVue8<~{Ak`%x5|%#6k`vWYDOvT'
    '4;-6g6L9wOlGEQ5>EK<(dlE8L$E~7F(bw^K)U8jKT93ln04a*qQ@@AFQ<2T*ZaL!6Sl+9PogNNp6CJzjEm;aMLxm)zQYAyRz*b>X'
    '+^nlxLDF26crOer1o<CDqucP%)5U}j5s<QK0UBj%K3cEu$9YZ<E5#$pjGD7m0%N!Ps~g0O++?JnWt+eO;uES?0JwxY(gWfqJ`3}G'
    'i6q!Zp?QEI@$fW6eTy$UlQ(+a9}4afq08Mu5y8Xz0-e}Y7j}t#3CbdWfQG{|3p9#KUpj`s$3(SgzN8gMI?I7Q8yUtKV5_vzUC|&_'
    '*u}tx@S)-~dKEpab3?won5Hfe&9+OcSV)0%!0yKEA;h2XX8}%*Ze%<1_8}c-c+Jnkz(6;g*eo*q&VYqsqIO-!h>u$v1h$+?H%{c-'
    'K+>MPF~Xg;|6Nzz)g-HH^stNXl2~x@(Gt_3>3aUpS<O(>FJ)2fV1+KDQ7aG&7=A)Cs~7cy&`jU<ulIW^G)VMt!x&p@?XvXQgDtU!'
    '6rZnS3J#prXe80?_6jep1A73;qFscxyp!dvsK@r^5uPVNPhV-voRYuHzgL(K?GTa+mqzjKB?+Ei{pdN<%d;BN(ouWt&$dp~yG74i'
    'bEFwvawtrx8q5iAGu9z$H-M*9HIZlFxqLTK6$g(<3Ic&u3T9=N<SvI~qUS|Fg-Xz(iGLF+EaYwf(p-hIamyL*!A#~_nnnlIJAmF|'
    '&lWAe9WH^ZmnUE+7CR)PUqj~YF}JujWyDA*1a{A!473X>qL=9s?L<*GVty$A*8*N7`q1Yw;($Yr{z7Xa%(6Ox86|0;5(QqT8{Ds^'
    'ZbspZmczq8jCUm*-RK3yOjzy8Ufac|6L&%;q|y83hmxhU+L%$H_!P(wEHZo1Gj}lfEWT(vyJ&)xIE=5iqmzf=vBucVu%rRx>O*AD'
    'y$U3qne3+WT9_V~%|;8138^%lX<CANK~;!x?}?KGDqE>Rn^4s;<tfTeZY#$wYZw0_6=_81XAKxrJ5L`(PLt0k&urucG$N-8^q8NW'
    'K<&j<V=v|Fh5S2-XOe4%{HMJn8hj7ZrX~?-()@04W!(nL%nTvzFS7>Ff?qaH<nIVc>wvAfU@jG%6xJ)@zjgU>CD?IZ+=gTJ6R-ka'
    'Yf3)mKLgv2PJ~itWf!qic*hlmG0`0{c>h)T1{0VK?quY4$Gisrl5lRd<~PR9SR%tYdF<6nOs>+5whcnvy7kRNPxr-!rAk1Unc(o#'
    'DXf@`^w;5N{z8+M-Jwdby+w%yz2&4~HT3ZRQDWl5=!%3)#Shq)X}Yhcv#u-K@?jYLh|K;F`!OXsTU$~+QIv7EFM32czb!R+A?f<L'
    'dp>K@X^K|1Ol|1A7wI=vUxX^TpDxQNh8IgEIPibRA@835rXL&beaCv$@J*;fdh70mMO@<AJzDhlJG+?c48Ujy;QeoRpU|0-@Y}<L'
    'ENBk2LR5@MM(2F|^GcwhT%HenvVgTM2T0%RBB}fL$4Y-U2Ro%AVVqp$RG-#Z{9o3Apn-5DolbYJAtW`d>1PF)B=7(Dyig7A@i*lP'
    'FP8w9TmAv*E;Rwp5@+;Ql#Z(@#tUNCRd3Rq5(hI42vmc;sIhy+E>uH1?P0gDU>KsDy}GoFg5w_Jljl|z$#pwO*t14ngWEBSuHi{e'
    'n+*A!BcCukiWybdmdnb_aClavJq#A|ffa!hs=o<}DNWd`+l+kJ)YTqi2o_;aji6KZMY)=aB5dIV(Wu(Ss#lTKg-cVgoNM#)SqWKq'
    'FF`K_^EG1%py$HH3lq%8`Mm^2$~fT@{XS0WqDvG_yOMAJ;~`=sr4z6^aaEuvWr^g5@rR{KsSfYLjRR_tn{+o|#*qiZG;mSc<pZ%B'
    '=gh`ar-O~H1xF1_PQjeLHe%bk&EC}lr1Iuv=k4Sy2MXkQLj3XqW6P<KB^-7P`KEN?x>7-%c}MX<Yh3=Rp1AZJ@Jyl6Z@$Qgs;=i|'
    'a0m@FgRy7h{^?8qoiN$wI`E{d@@ID7eoeNfr{HBh;zbeEPPbvsXXfv8`{mZ>A6*pFSNXB{VWi`r_uB7c6G!>wIvp`lu2HFz8|Yeq'
    'c3d$p5fkk#4;v2ahD+5qwWYPwLX0rNgpB=pVqpfl<l96#ElybeaCM&Ih+RN0I&qnaLs^F8yZ!*-SF*D=M2Xw`%!y`#XZ}RFtWX6%'
    '3E?m0TQN)==;)gxn)F4`q>f3WdQ-d{^3474h|tH<xbzB!8GTrIC@kL;8~KKXO{*%C{S2+zWWGslvK~yPmz%&N;}r-D_~lGMgkL;j'
    '5CbmVuS59II0|+gCa>MenIJ(hv1G7Z+k_oTT+3#ObN8@L@|AQI;offv^p?q~sawMpG@*s0P&|I|0p2+Ti7lOBPr$2m^ddMjJdiW9'
    'nm9CGhq;f`{sFs&H}RWsP0tDCqnQ_39xkAXF<G80*0k40S2}SYH?V0K!C_*)-1oNUV+ssjq(ChGXmLZ`j=v~kN3Fd_F6WM!mRmb('
    'g~XHcZz~Cdz_1YoP?h%BHs%!L5>Iq#D*<e*O>K5VIp#u^+}!(ua%-E!W0^j6JR<X_hc#~D@^`t9afp`Fs7oTzTvl(&foY{A=(9!k'
    'gdT*!@L_^pd|3&|lU%V}Z}ql6m&%RMjw}HBPSvr->HihIN7A~Ua3HhN1V!*@&1Gn}#Oy)MdQ{FlX{R#b`(KYO8T;bNwHY~@W-41>'
    '^b2$m5DPeq(zgBLS9P@UraSRN=NrBeKASl4h$}qwIKUu3%@%z3J2}nT`s<-CnJ%q+V#*r#$6vwCN|Ckq*o;l1rGaSW_#NO`<iB8H'
    'TKP*6zKdw4Wg?mM*|$9A{z;$xrCQ$4?`KSB!Y7RHd7T619?7yZ`XA6U)syzkwa4Il-8-?oQ6~bk*Qrmn!d+H-czx&KK2Fx8I{3d!'
    'ZwLmK6#7TuaG@K;;V&J=a*~-Q@%BoLaj%l_kHM%uw8-40NwnZ5#6q`5f=;ug!DQI>TKEIZmoBX`rJEvpvvLJv5F;nI3jo>Ue!wTX'
    'T>Os0eL9H{&;;!j<y>L8{oPCr&m9AO?4n!is2<s^S0veGVI&nuEjCZnWRF&tZRbSNKo0(hXnNXsK~hO40ipHm(LC8vO4@~y@#PWl'
    'xSR;fa-^aluzZ{$RXl9gJb`mO+i?^UQVj=?##&JpuSi;hqmPo~M6M5XWx-FXvdnc21(Fitr9kf|=J;XUaK)3TY%()1SY?}8qZNH@'
    '$}f!F1v)hLwuy-R#MF_03tZl#2&P{uTIQqcy(ru8WoA`_4x%W9ZE2;w1q2!*6*Cyqpi4R6gezD#W#CBD_hC2U(|c=?cH-XAXsl%i'
    '$<(KpV9`MfaYp`uT0NpeG;@a+@wU5`-|0w?tq)d181a&Xo@1e;m6U~!o3We+xuP_5+;H$zXQ1!yk+_$2^YB-EgehU6m#0i+e)qBD'
    'nFtSQu%<J~+$J*GVR|VtQh45<Itaap+#mpaj4LX_Bg8af7h|uhb5B${!y61)!u&+;GEol(Y5in=^l%A$1{1iFN#1-2QFc<V^T%No'
    'UZ|%iBmL*Ivgd&#IduqvajKoiKywjK`wGVSsBf<P)$&vB)nO2ns|d%_Q2yyy`3-RkNhP0o6JP4MZHn~p3b^8mP^DxmBo<v_fV)&='
    'ngqu*M`-VbGoUZ(yo{9rx0R$@3LGosaWOKWg_SG3<#5;SOzv@%2g~w45!SVZU8-MZ{irVGCB$)imK;<Jmmd^tedZ&|RTs)Z)kg)('
    'Yc&5F9%#hx>&%K)j%x%MjJbO+<%?S(E|zRIwemD=8-%$%lk{^t&en<%$Ek)~R#sZN#WV@npd?=ggP!+z>k_vH*mffX(GbU@_2n!;'
    'wgRTaqo&<#1-*yIi*ri2tFZW#eo~>r;Ga#@^nKr`fhl)Z6e7<NHrXN5B*_9I&wR-ct;l{bQ?@2*4g7OJuU4PP&kCT7$WIY)_=|$A'
    'V>ZIcwOEHcf*f$Ys8c=Ec(=;@A7e^8N6Aw-6N@;iedpQv@W(6@R^z3iSwr?X6THfg{gJY^e)b9~CNFYjDK{o9zSWS@Fhp$|3p57('
    'gD?**#aRHgf9EA#Rd&Vi8Lk@l>s@0hW>ar<E6#tMxx(n-XD*}qmv8jhIQJN>={3B*ccmtrcSORxHyo#(RFb?0&Wc>QdSleNo?((G'
    'AB2))znOX#sAxMOA3oOa&+mk_W?5)p$n6(;GOFwDaIBh3tkqrYH0<CjQmiSya7(4k@MeKjapB!<q<C>W1b0vtrl=tQI92A=APeLf'
    '_`KxSR3?AhtjK2ZA*WM!su1KTTC)sCJfsJz6KIVcQf5=c?l?jY2<l>>fwUzpCjyC@P$*c^{+7vG<;J4WkwN62nIIr;9&}I$sdl!h'
    '*@Kfq^4C4}Zqz6qPC=!m2k8MWkU3;bKb~aUd?^DJLw>S`XO!&4R<(-T%0!R;M_EE4$51d?y~+JTrZnN<uUR^9^MoXOWBIM|=7U;!'
    'lm?>l!QEWR8TD$qj$4@~K^&NN1@q10mI`vBT4lLgySd2n!`}a33=)@T?rev?_i@c<7apsmVopS>eQvYiOwm66|HqAjfpz|>Z31I^'
    '`p(WIVJX>Fk)iecM7k!IK#hxKX<2ACcVIjcmY;#$*X(ky$E)nvGK0!d*w)aGCvsSD(L$bIczl%y76V8wWnE+myv-QxgGf*9Mtl&z'
    'jS6(vR0KXYL9Z{3#rR3l=`Kw+P!8gv6H_|G;+X)ASj>TLjRf^DPI>6_c<6MY^3dVoleAW~0Jp8x6y`GpU%qyfT~+7cO6}|3fK|L7'
    'nl%!KG4z?;-m<4gXDt>mLt{w5vruTH(T$W^7YtR*c5kjgcQ`p2g!2fl2eAk-=fMUmmV<aG)|+U}kaVxFFGG7T?<bf+!Gp$tlt8XI'
    'YU2svtT~NW@7h3#5bzvjvR#M07DwvMhXF_8C$L8n|5^2LcAt`I@K(iT0e37?gl<rES!{a0m^|)dNTFx<c!c7}XyRVneyGCJP(#xd'
    'SzB%PRAO&^rLvwdOZKwxML7$DoVhuotJr=-bTyBWOZf%c7p#ftIW=%#*MKJ4SR1i-cAI>an2g39T^Q47$7?R=JK6O|Noruc)*yH2'
    'vrb|h^Uw%IDV6igJB3<!?k5(o`Q-k3n)WR#MRbYiMChRS_JMFldLMAJ41E&!zR#HaIPBpmlQn2{U+ge4JXS)3$t?{tx?mH}kXT7S'
    '-mDSyPg6RD-6_$|JjVkw5<&}&nBw86qXd2NhsGFJ1luCAW4E>ylGzZu?_8B(F288&q=Okxr@M4e;Fb9Eiydt4AInjd7353UD1r{U'
    'e1RYG`Nvn(t=b^><iJP9<K6?P0ZfEL9(}=nLuiLt$5f>2Tq^S1nN8Ej+o}+kWH(Qv-4<pabtP?uu*9ay<FsVf^;_RA@Nl*Ohtty^'
    'HP;yD`GmyhrSrce7=jlJBZc0*i*w%gX|<jb4^G7}k9p)=Gg{(w_UC&r6_`Ijic0;a7-oZY3tfab@yeJ8Yt97DVtA;z$&X@=mCNU4'
    'O@yr>kvE&pCqyX(HG3-0gGfAl!0r8B|B>8TIPK@e1Dnm%$(2O+b+@&lOGPDCtmVbtlsoc|kKp^6CjXc*OrfQcAn<HYFWuHg{5OKC'
    '%;@1uAJ6nX3P$u#&XKGtN#VjiDqx*;lvIz|_J2r&qnpBHTs$0&1Fd~-yqf&RDz|$deDBgG<%UV}XNv1!Yk;Vd+~q32mENc>bpeA0'
    '57r(1{EfCopd3w99Yqme>j&^;@#0jP(wg_8Npg!Ruy$Gi1>(*n&&RU)R<443{no8`CD{oWV0JIo`^!iI61AMhj>9g(q!n)A>DOS5'
    'jr@2U<!Q(pG+MeZ=NgjQ^wy(5UFU^<CV{wV7HCFV;wy&-5~otAW_<{Jt4B1z#H8g3;!2CqlKT4|4{tl-+Y$>~Ip;|cawZ>up?5V{'
    'WcbrHYC2)=L}%Tn*E5rth<J|JK2^`d2h^%SFl^OVW70{MTK3YR+VPR6-ve`31)MMxXbF~4alPD_{6Ro`dU-k_`pDXEqK5QNOx&z3'
    '*6}V;q=&p|0Z7QKV&B&mZGlhs(=E9gGZUSju_d$vsiECMP`iW&J@{*wS*;X=M_;E!sNgwG_nQ3g?ch87*<A6c-x9fF^RUyrS-10d'
    'PPm`6b7^+?mm^qGmTqm}$xe7j9OsJa)Gqo9)O%!$>&ES-J^WkAd9xso<EVP*F2#-S4jIEKd#J#W>3x)7N9|4je?yL~Wn$G9nLi~n'
    'hC&P{jKv6n?RKCwWz2qwi1&S`bU7%d?P$Jn*!DP8otbU69A<{&8K)S3z>jIRgs*IB6DKf;w3f#0w!gS332oPHsdnz&tF9U$x}`>&'
    'k1?QeDlDMungxp<a9>5&jc$+}f&BYRzn-vc=(XgSgY?^3xtwgq`kE8Ty4guo*@f&8!A>U1n_{-RM_PDL^Er)aw<{Cm0zEF+iVcj;'
    'g*-IDa-|wT9C0r~1d$hh(95+JRJjbzG09i3+-$g3!niL@PSL3tIQ`Jn08$4%#u+&RdY7qA>R|tBgdqC1a*wS|0;s(|PDVJ00%A$H'
    'pxf8Z@F)!2a<K}@Kk?Z@7T-yCcWx^>_VCQNJ0BhQXp8+0Zwq^+<8|@{tYSo`%W_S&fY6XhKqT)lM85-wx7+AL{zibP{a&E|7|$lM'
    '@}S3%Ut(MhM(}?|bz4ow;CRui4V0W_xhSEwiJzJFB24!UB_|3hu-_gCb!tzURly)JnoH>T^IqoNSdlkft>^*eYk<fYDNBQen*`Yr'
    '7ugOcmWFZr4H-1aKP<@k!FbVPY`nOdRC@i#dmCx85bnxG@T02+w173J&CxL;w6RNrh3HQ~@j)veIWMwxWJ?7foV;xN-;Tonwd>&q'
    'c~aNo+q`)x!*)h?V?-cP>`PHwn(I%QnCH!V2ld_}s(N5-?p}sjNMJ;w09KT&%^l@)L;2B8^vE=+XsQm|y^(^L_QSCo%@7uwC1Z7L'
    'bKFs}P~AcQd+zYfozY3wEiv9y9`|6{dtQJc)o(T;i2_o_&)lGZUh|}NYs+BwZ)j?s!eBb6a4z4dFUjyUgU`xe>YAp3sU?G<{BkS7'
    'XzxF$w+QYs!fyn!1n{~eRiR=)Hj_8CsFX;wj5D^4i(i{IU&SyVUW!<z2IxzsJT!w=eX{9yok|(6+dIWe%XF<-q*218I^ubnL7+gX'
    'NyzHEg&z!1T)TB$=<uvUUzm{+U*Mc0wMwfVw4(&pse~kyI?-K!)KQacZT3;{)Tw4Hf1-^hOzHPPBb<C{E5_-9{~?C<UYcYa3PcQD'
    'Y=QhjoEUvIFjH>ISa=1x)}2}QSIg1h@i1<~Mc#ZCr?N;WqAoj*^2C7aT80hMZD%KR)&xi_Y*$Y>mX`>KVOfXn`F7ya3slT41Nar9'
    '!sg7Kj;tVF%M+ZFJH)P-8tBo$)lxtGll0SxfC@$vtsWz{OZz+^>_cv&DN!;d`DDZPE>bPHoX7D}QbRY2Ihqn3A4Ooz|6xIOn*$L@'
    'yw&ubxuzt*@<H#4>_3}LjLc`HG-~je_0h9|VYz1hX^80a!i}$CN8~pcjwt7U<Y$@l!_}RBT$*Ae6f$XQ4}<gvdjr)2W!hXCYLymG'
    'B)l~|Y4#>6dwvo{hn&g!X4xnDG{gY1h)ODvvtxB}j|}Ld<YM+8ZZ2K%V0WZB*(*pu`ht2X47?tP!L~o7T5`MXZZ>)EGnW$!ygifm'
    'n$fX}rU#8TK*It&;}w(27IH}+T!G!0P4P{#$M(kJr#0*D-_4U#kcHh%Z%Q_28b1g#*LZP9UDIb(_g<mw10P*+43J)E!&6s=62vbl'
    'BYYYS1u@%@22oi2fB48BBkeOjq-H_}=w2KFAm~!wf9I^Q+LI8a`)J)QkMHLsbov6UdOVe3_n2NZz^^0B!Zo2>V~?n2`TzX{fc=qL'
    'mPGH};8wNjB2kIwjmV9-kIESu@1k`9P99(+NAmLXpi}sv0H6O1q=^6lXFEhNhyTXm40<2B6i@|i^-p;b>ESx#pL@YeN|JMaJP7-Y'
    '-<$;DGACUw>$5wWe+lZ{$B4S$JEMA<AC@(avng-^v*G(^^KbTaOdBQzut;2~Eu9T^C{C6vsI5nkm$BJ$i`g+h1hy#praQ+c;Wik&'
    'S#Q5Gfj?7<I%l7&j~V;R73-%h2_*eMA{_HOT{zT)R>gyenXAv!<GM`OF|KEc*I%~31bA+gopWaSR<6oQ?3i1j>LhcmkPCEK2xX%}'
    's{(QPse@@EloPE&xSVNo?L)8rL&MW=SAA4kmSq$bu=VqlesG&<=}}4$vC1}U*Ggqf(CVE=hWe2h^wT`l7lD0&pr<f;H9n_?5rO3P'
    'N)U2dl=`mKN6Z}KPk5isthX<<n&cA<6<u43ITQ#9o^azynznN!NWy2kc41<vW7AAn$_4bu07QC{m5D1Mq=bJF-9}tTrWuCit*!qm'
    'GIAv&F=s3RZy5|Tz*V{$iAJ<sB#fvSEaQ%!Z&37FRM8pKl~ped;a4Nlw|L5>b{biz!xg$d^wc9o<lx`l7TQxGY?mCi@_Tf#hh=3b'
    'K5oIDZp#XcOiHp68ziXXS*Zx`Uf__vcoYO-a4z8Jy|%FV0FC1_W@TS~_f+qjz%ws94eEY{H#G+mUPYR|sAi0?Z8Gf(=z?9xY-c_N'
    '3(>Vvz~S7x*EXoG={T@&43z`YN3HnXZi$U5c#iDwsZU_X2db>n{=IjN@|6txTvL}3L8G#uOr%9j5z?s507*C<NyVE_BA%AUT^>Wq'
    '(CYC$O0=}EdQy(vzBXZ4g2E3G{6^i`$bTUmmX5HyAOTE=duqG*Q5Qh7{+$BZ`DanBCdEfrgmQiySwmY;%XSX(A34(zi1NJ+vEHG;'
    'X`wlU5%+X)?TTe`9Ds}yJ9$_YD2ISi4?fKn4INJ`Qv2>P#SWN?e`gsN^RbUlB=}S>*oo+D9&gp9f0>tn;7?YXu(0}gJUmA*G*vSQ'
    'ZxhJZvIvh{+$CUXuN85c1sThu#Rc)~+3sx`ZVjXORHjIi*mFn?y`4!gxg|qHbslW1X#ac7G<jIPN?;{<HwOtF7qQ}jUH#E?^z-YD'
    'SDE!dBC|_DTB8QZ+Gcxj<%@9uYLr~IT6hQsFe4OvO3-nXqS;@ok^b#wwX%UQiHY`#tXq&`^6l%&pnk^a9f>^M=fzQgAH|t`&jAt}'
    '2F+n80wY(y=OyB14}k)3q6@bX+Ez<)v4CfM-SFHHXHyWwnW6{%;Nqa3DZQ@E)3EoweK{j!T>t}bT?s&;uTCQK-2mNysf(VrAW`EQ'
    '9`rP*)?h;>rCzpw8J>KS+3Onrt|1av0Rc|G0!MWbE{DTX>+>yx-M6yQ<A#C9y<-g!C11bK6q63m(j1fSa{F&LSjC1Aaz?f#$JB7G'
    '#eIyX>nJkjgqMfZtY0OtuC;9SZ7zf2{!6VW5nG6tC#p1dWO*NJtJG87$*h4OeOS9vl^X?V+`^FO!Db4v#k?>y)vD<Ot^i<P^BEd='
    'm33!XFHwkf0LgHW$tVg?dR&!k8MGw*o_NOrJ^_S6O^CMvqWFwDn4eT&mH@o&pWV7Ulu$PO{zkGw*~B{N9iQHch4O$E-OA$RN*<<X'
    'f55ERe0D^B8I2!Pg^ztPHGC3>&{%)X_MyQCh8hcvy>`<h7y9eN^&c%TCj@e(jr+mOE%;}}a<;-dQEk4W_RUT1q!F&xe){WckMdT9'
    'DXD9Sw=hx8=m4GtJ01REm9_<SY8Qsgc?O_evXU45SVW^glTt&OF-QVIzro!P*xf_@I)a5Zd`I1aK+23g!tBk*<jo&{=I{OFjKI)9'
    '`0eo(`eG(`(bnjL@TnY2L}F2el=TTjug_FN8AZxR_65izc^GiZsJ`Vb{<mMoUgjZSC!bEUG}Jj2T4Qsh@+TGD$`nppqp7`lmxN*J'
    '{XgghD{E~K^z3(IZ+KV?1UCUUnuFLoWUB+Mtp_x`O*w=BDfE`Q^sQs98~M=3(x6`NgdNn4CQcqLs~i)pe#TvIj%p#?<-VFLdpNqk'
    '%a!pt%z-pxCUiNC8P<s>EK7LOEEky(;*ZnN170&#+^>eLJr`)}AYd2XA*w50r0Kt&FSJxNTo644M=9NM_|qj3u(23e5b#k6kMlE0'
    'P{j4hbnW~@bTykS2pb8_(V}ihb1xA>UMbg@@Al3WU>f`uih+9$@xbP5_u_2(w>e5rr&3mYd)2^*PP~tgkYx~r?4~8`3E+W1s;{^r'
    'tvT2JRyaGXV#e=Tqk+`*I83i53*6_}ziq#oE>e3{yT^tOoS2Y|`o7*CC*g!9qHsJiC0qoJvM`>NMUPG<F0RM2BsJGh!(409%4c-4'
    '_|F{vr<5AbF`xmWIvfs~%*FH#7WPdYjT28yY-5Ut;zClJ?BATW6rrn!As-Qaw2d9A4{-R5V<et>*Wkqjt-br{^J&o$UAT2g4rL_6'
    'qw*1ssjOo8Hjcmf5VR-?%X>%yn~-iN!qKqYYNF=MQCAi=l&VE<!!n^5F|A7@={zr~;8c{+vK<#qaJtu>d_|wOO1Rf=Xo&AKa#-iy'
    '7_q~2rN(B32$QhTgNfPKKTVWpM-$#Pxm};iW&%<CCpJ`q*l{~yxDbCQL}!WOOn*qRr~F6bO>Q;_u-(tHy4!ErsR)nb{0M1nsg=rO'
    'wqZjAtoCoL75c*?mNPFDGXq#<DNZn^9AQO5Qrs#D0*70CYYn%c9f_OX_@WEuh>le+VgGbUhbea(>~RKLA|Ez3LBAHUQ6C1$rW`m%'
    '_U(Gcc7grDxlXyMj=cKth)Sru7USc63ZiehA-H!cZIh#qN;CwLSUt(>V*Whn#oXw^XD;Y$&Z?5@Gpm=BPk*eF{z7X*gyVqq87=-_'
    '#Gb)^LvV=7StKt93w#VTooCM+84yZFba+s79YYl8ER%xD5U*&#CA4_9*Oy5Mx+}w{AE^!9z(QzRl?<mM3<ut=^_gC$HX(g+2=YKd'
    'qS9dDoI8tpwmsGMi=dUr{U#R%lR!=cXsk7(P)54gtX$`lhSAG~*iW9HSg;B;QtEDJ*7<K*HfOu73GMkuhz|KWG%B5Gp+RH_2ylG)'
    'P!KaY68%cN=5MH5%*Br{rFjkx)z;M|5M)oro|&<6keK#ur_LmeN@&}2Ip%G@ibEtBrmePGwbCPzQ@nYqtrI)QjlJfv@1dSyN>*8_'
    'lnraVrk}ZNIhlEM@Sxz}wM{hGFSp{dGsft-$_>lsMwp^M2DIFr(4_dkY{sXhsHf9*L(w=_U+KhBI@p4P!u4Qz%rB*+3hZ%qj9!`0'
    '(MHsPct{`3dA}*U{U~R5f)o2lVqV$VH%3yT#tr&i=VPYAKVh~U#)qBKw4)A?xPk=4N6j~>6>0@!Qw4k#q6!-;fSS7~ENSsUeog9A'
    'EK{gt{m@cn5GmmeKz#IUFe?qz)R2y%|Hf{%gE`>w29fn`2d|XFGLe>6ENO=)9n-fU%@?aHJx1WgA1DYvd*C(<!RQL5(4O%!6D`?M'
    'qnC`w6i6vU=|>Mfbyj0Ls`f&W0!LBg&n^Ee<aRDcud{g<qKW>|e`ns5{dd!vdV_$C$WDL2S1oW~OFQSqRg$Om@rRi{6a1pyhZCnc'
    ';r4A?RXWep>f95?`7bL?4he{7!njOI1q+(*aY`>Z_=$^vq0Y?2ISxmSQZ&Vc>HfBfZuou=w}V=*NMr*l3oEe05sP}!@%Er@fY&TT'
    'PlqMPAWQ1Y(z^-R=ed{M;wKWIAn5Sy&*>)WwP+5xo%nkb1xTlMVD`!fM@~`^{Typ%%MaKcB}2HEn;Rdm6qI(R1U>PZfLZc451C2p'
    'RiguF=;z~%3tkp%ePvBn<|qBrOmnZ0sphKj`|WEhZz<%T6qp+0nj3*gByb@v?;TaeKxeotWRmUOrYrD+1%Uy*A)aV_8e6YgcgI#T'
    'mzXWSc7+Ekb5$E)Rxy<`9t+h!Y-{Dm(^)d72r>Ig9as3gTeSIgTN9|jMQa6M_SEeCug|})fmQ6*pwEx`9W{{b47U`9n|<aT3@KGb'
    'lqhfJhT5Q7u3@pDWw0S;p|OfS?P3*6Y^ztz9N5RWu*Sc`px8`3VFpHW9d*{H72t{<lVw4rf3$e{+;oEYyvZ50y3C<iAWAgaL(vmk'
    'S0H4iLVLDiiQSqc<GHqMnjAszfXtLP+nV|Aq_D$?Sz;Tl!r}qt27m<5fHfb847Ki9(6&ezOgkGz(L~c3^Z9xBy*$#t?#EI|Uy-p`'
    'Ndyo=bd_-?n$H--Er;^J>Upv9Wn`L-l2*#Bmz`Mjovg8fe9k>5vtM{d3&Ya(bf2LRS#jSY7NaA14&TUI?UW#>+L9Y;C<e_PR}%SR'
    'h?m<FSA`7K%tDrsxJxTbCC=k!w+YHvF_5GXQz`r)N9HvTkM)MPc^Il8s5?+gc3~A9%3H8L-}RUK$YXjw;FTnqL8Y#Jg;qE!3c@N-'
    'P|EZ2XCn&Uo%m3HNNS)Glhf)}f>=|fmpQ;^21K5mP$t1!Fopl_T~j$cCYDaiT#zv})>ZFbZLI<;pQilh^31+FET6&4i%E44u=g?>'
    'jYY>3-Q_W!zg?KA?NB<bVL?8l-VX5mk0@j@HS<s@zf7I#2B^Ojl$A}5LKelp;Z3b*_1r$&w(6D!Rl!mBB&#9BKq1|r84C$@#VgFE'
    'sQ}s-S*Pv-?f}BDRe1SrMTRno(x*ynV{1}q%TG={#zMmMnir}XVO;eP&!U#mW17zY`aT~<Q+j!5rqKx?6qahaxm0!pCnz&y@-n+E'
    'A-by{h(_#5exApu{SBMU6_jpNpSBkt0_Md{=6X$>#&<YqXRdLTX$3}zByuev`5*$;&N3P*J|bbm(c{e5K#aYykbT{rm8Q{Den^I8'
    's=A)fXm2cp0ZU0-zilk_RtZ{hok&6ilI14O_0S*dF*)K!&U4m8v=G5JDpFp7^qWxO0Jp`(_Nc@0!7vx{;Z%|oBR_qIMa!&~H)iZJ'
    'JMg;+@PgNZzpS14Om)XNLDc5y+~Aw&MO@W9CAbXsB~IIBE|O&8;*kBasnjLr;I3eJsc7X)65ud<(4$+0S-M0uSNbqQP+&dQzGZDW'
    'mo-@5a~bJ*Rl|oNs@r56W~krm2lJ<5ptme`Cqap=$0HJKDDRnqdR}XDR1paZ(b?;}-{K8W9|ekiZ^bduXOAF#eT2y`&?uD}_+B#Z'
    'vra(|8Pf!6A!j^X*y4$iL@P9xld!;bDzBhKq(@t4NQS-aEMcEFI_qk#cZlf9JLLcJNFMK_B?7aLuHR8*affthZ*!twDNnggR==~H'
    'V$o#Og~0uR(P(G}=EAUa&S})kKhrU?&OZ1%pxJR)sF7dW_>UM;15l!Lu*_ZoE<Mg|fx2zb3MG!86*GP0;3=Nm7QX@zxKSnf)@?~f'
    'qwRjGB_#J>k>CK7Dzzj@V-T>=J?sO$i^MfH^8MBWz~;#kD+Y~Wx}xA`9sUVcnvIl5HEo0%yuzT7O$K}Yu&2D8iMmqf2eCOHXPh79'
    ';-k83Kk|>BQ`~U^z^JfWJQjKZs*6oKhpI-iYf{Es8c~>+VyoEcWmY`k7%Oo*W_z!pesPTVi6c1Y&5yBa!h`N6d}@h`%$bi#ViCrI'
    'jkw2qz$Fk&0&(7D$>7U8N4H<+aS){XDsRPhT<iY2gf>-=%tOwA<X|~INr-Xy4{liHx#=daZ~ChqgVXGf&|+I>#GA-Aa_{}33uPc;'
    'n4rs~E*!jxFts7a-TBh*z$WxHNqoo;9)b!z(uM4Y{pa}0KYgVBWE2q6XlsXDqJaX%T@h&X6~IdUDw)|Ar<^#(`D#nvNtb<}JQo-9'
    'c#lPv@dlp_&@F{UT%&!I^US8B@C15WgOT%g4;s#`iqfd282!_03@+HO%x<_w>bcl&tEb8NCh2_c(uQI^oD*rVmFxvX-KTjA|JaG<'
    'e&~*|?lJ)KEelH{nGp@(5t8hnuTRd(J!FNP@|~ITV#rHw*;VG`{oJfhMIfeL!DrvzkN~97t21R9|J}s>{e{6<Cz{K%oCD2_PDDDh'
    '%`ar!X3;k<M4V-mR<b$lBo)rG#IzJiEq80n$-(Mi7>c=9Sz|&vmAHEAY<X;Pvpp(9+{DSYxAk5K_vf#4Q?!HNVoBS&?O7(EpX-oJ'
    'E#GF>%47rBu{aYs2BAV+BSj{ZqDEd2QK!s2kvh<WKE-BkXlKAiwj%`4wdzrx(Na1~_P7rLInI1-elDTPNMzepdg8}Kx^xuu!;k2q'
    'JUEGFopwL|-tXfQi%7;IvB*Y`YHBw#*;m{l<p};|?y^g0BPEu1LxJ8nEWgzXWagx0L&wHOlH;at)^KHt?QC6J4KLLlLx*_T_5-qG'
    'mE$IZK%)8Ol$G?tgm?1|Vjg6zBu5)of{1|;YT1r|?2EJYG=(g~`<pzSnv0l_GLR1}Q*aNF3lGhI+htqE`407mi$Nb87WvW264<W|'
    'W|O`<LZ4}DFf06HXUicAm9W-8r`Xuz0F&SWX&lwe@&y{}fuJ^}l}C%r@x%mwFf*FuSa)lTeJZ|K5Nb*Yke*_&joMo{V9pHvd`g)P'
    'BHHl(0b?bdfN_x@@o5C6J)I^_LFZe<r(@JEIO7gK4(Q>RmBT|jIJzv^u|QF6dk2g!h}PSBLE(lA^|MzV$RuiPG<kdWg%3$2<CqkJ'
    '_bEZh6)F%n5U($DO9vhm*ARd^3cEop@Z(?++?}X$4-v4I4~^C6s)L8JF&-$p%~y<NY-yeyVDBcq9U&}rz<CH8>CK&H8$}c<>dTvU'
    '9oKT<2mw=Lm=bdSFMub07Cln=-Nd+C0V!)IhG!GzXin1czkmdH<mH<UW|}Up;nzq5`fB4KIx$8*To!ZcDMxpTx3M~6-IT@p`l#}p'
    '7oU&_Xic&BYMGV-?bW@XiUXQTWI&SAlZ|cD*znNj^FOo{N1tH~Yz>S#dYXJ$`sc+<_Oipci7+tbE()lCE=bNjzgQerWfg{9s?Kgv'
    'KGdfGsw}@@Q8-)TW+~?|T}9(DG(szW0V5S^nbz{dlg*I<em%o(AV^><^0%+slxuTPhu~*1la}}{R<U|4_F{1&F7OCW=ndQ2%5+eN'
    'Ucz4V`iIXI-%Vz?M_~!EPQztBn@36db)ZA~0z`|pI|9>iyN<570RYkvyz5}G`7Xl><Z6|%Vp3DeU-uS=cLp-(>%t26Z7Q!xFmQ%J'
    ')4caZ+wj*w!2voXnbAy6C@6tpM%~Z~YP6j18*}mDC3-<q0K&Zhi!^i3$CxsRK49nu8(qM>noM=?0c=@MGo(!M%H8?W5be|>HBI|I'
    '*ThptGsN){yiNO2{OY7E+vf`oooxm&PxFNRaPu*Rh8<dh!+qxu-dBO<2J0^HtKqKN^ST)uEWsE7{_$G*K2rfqI8pIoknlx>)(^;a'
    'aA?OpWd_F2RB`ZTe)vqngc8pIqlD^b26<Fh(VuYJEXGXgsw-SVZYt}N3pG*a0*t9{wuUgD)C~FJQ-fv<UFaOtb9lf1ZDF=mS)doQ'
    '`9W0LGW>E)cvL&}<@_W>N*0J$zm_H<HEZ|^1{)9bucAP(`@{2RvUkZ}YGU)K|974{xb;*o_hG1&>P%}3@K%ET^)ME!fV3s<0&B76'
    'ODOoDaV{n-MoylqIz;tSQI9asI}6|MzH%1?X$;I^U_Qk3``}|FMURBU^qv4cKG!8+3ZZhcW=r*>Wws_d%{g$wiA`MQD@+Bn<4k$;'
    'jG;-TLx;;xCxhr<(SAoPCWb)%hK>QD@stwX$~qp(M|gVi{uqq^OKx83WTHr-+yH6CuTa!DP?_8QW1-?KrO{;HzX$IDelqFQGqBO$'
    'Y64;{Q8j~4VahVkh1I;?KEhGVY`H7#3Ix|TFG`IN7&wY<X4!%OaI}%-uic3|8Yp~sh)|=q24y8i8}`zU>7<lsWT!IpY<m;v9us#5'
    '1X;m6yUp;n_S7WfWdDbtv-ny2ufY%)m#QLbO|AA7g6ALQqY*Vkg4DsA2U8STPpaVdpRAocBL9{7x@|9f_nX*|w8*kG_d8_d4h?;!'
    '?}b`T<P5e060Er_x&xZdN`$yj%Ja6`si=eV5zD3Woc}1JG@8Zn1H9SB<-dWUCvp=I#}ZeG{yEX%Y|glf*UOsJg*r@dq2mBSTsd3@'
    'lf8z<ytVSTw3{gzP05k?eelmt5n=P>KQl}KoK*{g$Mru^r}t^5&JQ=Gk<|KfH4j5)M2Pnw?|B$>(q;I1a`#4UIMNjMSN4E2l>lyK'
    'qJ!UpgbIr^5lSF`C0_}yTB|mPsOGCDuEtyyv<bVO%4bNFq&X+a#hfxOBgAGQ%y_yLqi{0!SMLrDuO<TL?^m-IqKc`f0g&gzzDdRm'
    'I*@04szSxTmzw_l##N5!PzK#FXABrk8-FjllSkWB9mn;ha5B;k{+XheVitL<0KhSjGp=*-<Yn&p8qJM+?ZZ$dgf{%1ymz&TF|CBW'
    'mY$p!*I_*xDTPxSs{DMrV*d3lsuv%6G=eaqfX}(~pycL|U}VL>7o?FXCt#;USqq^vbN|!-F6rTFyVnrKw?OPTp?@$nihe{`x>38&'
    '0J9i|T>kYlT!V28a{SYfwN05OpJe#;7{O7y1fkX6_#yg6E|oZ3y3p;@1PzOj0FFM#uY0@hL~K*;!OTP8oUy0gFRW02l1-oR%Wm24'
    'qf9?0f~Pk}4IpQRHWoaAtPbH$pIPL?bq;GwtBG=FURNe48*4F4XVs274~`Z0J4NA#_L+F+O$d!IO@i^rMS3v_<>`6U6#bf>TkL>~'
    'qXpBBmGPe3x`3~&_xUov@!#aa?)I%o)q}hOV{j02f1h;!6uIKiR*O}_tw~}OVp(lVcSnlhyF>wuqf1plSQyARGM*?3;A_uDfdY}g'
    '_;%mfU%P#^_tLlljyC6Dh++Tp2n<>2jd!(isR>@U=#$l|-75(@aDnDMM~IqWdex<&xTw)ehr!?>65D_y0b#ph?wGEPVvvod_ltaC'
    'd@xip35zfEYqVV!e@hbf?j&4)3~^5o)1EAe0z*rH)rGgnaS38uS%pQuAxjhOzebZ<jJ~`E)c1GV`U%Z(Tg--z9~8mqkC0JR2STU#'
    'bzV|<PVLcnWwT78qyc_oqr?!;jQNLZNrs^Q2ymuKX_VxQoxfbWZs`iJ5Xj0J4h*T)ttxia1t-N<+2sZk)vO7N#Og5A^t)S`+_OVA'
    '^w&NxZ<V;gKYt!gl<_f}Jm-t3o+4M`Eqo%R3b}0a6r?GwBi8&$S$gyxpg;U|K6-DFfC@9JWj+yFMF~Nzo}fn3J4}Y_!eO}X^_)$x'
    'w`VlAOz5l;jzOICr&&aCN}$-GP`?+kZp%dD-WV)D0_yzfyOuR_XeY_|6a_zbOd-%8MszTTb46%iXb#jcnhdxC-a>g9mo6wIQ}=l{'
    'gVY<Pq_9{1;8`E{@c>=9d>G(YHA80Sm1nb@NlUa~ARY2cSgX+2(Lzp7VLtehUVni8BoUj31Eg7l){!i`&Da|JPP^)WJR3TOgG6wo'
    '#Tboqcw3Iv_J)6CGF)k>f$tu&zOFzdrN{-lNt7A5yOLPDN{KquXXwUqIUHF8cxm8f@XOk;?I^qhjX1wBnH0a4kEUpX3XaQu8|)at'
    'K*05eFA`D_xTuFlO(da-SoHSU>@M-#ddFLnG+$+C<#CVE&e{0+Zs}`9cZri^4VTf1;qt}MT<Q5YZ{RYs^^MeePQWVp-{0Cy=u%B2'
    '#F$zyz+6Jd;|n5GVHYc-WwFpR^PYF`r^*h=laD+b@~y6VG|kD*ZxeKzV7}_NmHQW^EBS~si5-TM?g7l`#>r~}z@9Tmu4mty_mJe5'
    'Xj-fJvqm^3HkdD=yf4prh;Stx5n;8&=B{*GTFrnNLd*9RXToOBa(SH|zvm?}izY}@nk9Lx^uy@}JvAh&WxeP@B`=2%pE*N0mJrDn'
    '!2tl<q~#(+WCpre{%16MCyFcl(!op%h*9d5O8;{phei^o`#rr9z)u<h)F2OPwlfXmap6;HxDOY;OHi<#Hr!RDvPN#r4JkyTx~IH}'
    '0x)D(5D^bj#K_b%vH6b^-mG-ZInl+rtw+`Kd?LbYa+N02Z-hT>UtEDR?;Q4vBrKRKa@2Z|{mzLTHbl3+9&K<iRf+OT#q0l^`G03T'
    'TJ^(hKAXY07~wdTh|I+t3grQAa$UVttb6=|GB_Yu6aG2Q74B<S@8nQO;}M4{Kxc$whTO%8$xOCdd{77WuoQ^5w8esOFyrMEC05w9'
    'g~zbs=DC>I+76)OUXB}71+U_BXV_7~;<eC(Pq)rG5)@buox__8vN;DKp#o0xG!0@&n`FI*VWf{bJf5q!Af1Nh5$pa`?%E=lZtK~P'
    'LaWtYHT@moozLK$>?LZraYC~U9RHEVN+*Ql370twbS!$vamC@X3<uUifI1WVY3vX==@kY0iF8%qqaXfHmxag7?`pD!?v7PzsS%n<'
    'U3yJ#ncl5|TD*5C)Q{=T0FRZ{C-u%($UWnaljwcF+&Y?(WHXrV>+p`@i>1V#ofszr5kjL0(ykC^W3g}WT%t*4Jxt}4o?%#&^qfxI'
    'W*P~LcN$EX6W!gK)B_rhyojA3yIJYSS%k2=j2pKG;#7O{^~~%03a6`mk6C{y1FVt034s+KY(8qPNle5S+LVhc_sm8!>ivkwNHvZ%'
    'a<m7+Ji%*zB+M!kp>uI9yqHn8d`WTpd;Xj{xAb|=%1O8wsrF>4g^!Nj^V2ui!$ZB8j{J0V%C>3LIVNmnlW*hI!zYrn7P1hpI?oZ4'
    'ySFvNH2SbaAsY}I!%WlNw9brh-I#o(HaZsxCWjzuPcfnj2k*rR-n|IU+`9z-ma>K2I01d%dxlqp(k)6_AxJzpQwB+TX8%z)s?JI('
    '1m954{8l&jo=~m()}`3|?zm?=X1)(w1XFZ5u(e^FNvvCn(lD4J%afm~Xq7BEiH9vH(Z1K{iI4$bELnp?KOI$Tn_l)KXu|z+W>kU8'
    '0S0ZPrnJwo{eP~5cw0<uQxz)5(&TZCtXoz`3%v!C&q32l&LSkE)f#2;@Y&h&z!tV+w#?!$*I$H$*+>oFf0y<DcVKcf<??A%!Kut6'
    'sCnuD*B5$8rwp$ilnNj}Uh@vZo8O&`lU?n`fU@pJbrVrpeBYuDC)m~9RgKJK{YeF#p&|031q8cXoK^i3iT850SEz^aLZF`A%}lv3'
    'xhyq7FI`1}2zft+aZsmR5#zV<SsuTG8nu`9k20d1k7BfxJoUWmM|EegfA6NM>m6~px>)KyOW#3M%nL{NrxQRv{+9MfZsW^Iv^Z;V'
    'nT@Lq>+|Rp)&g2$ya2*Ny#wB?F<RtP8RJ*;c;}pjw;Q)o6UVFiX#v^lbvX{}ceVT#kxwy>GEWvKFC%*7Q@U*S>Uf`|9(W?Y&!|}l'
    'Y;Jzc;+B8Rc6T09UiQ5<(Gt#o#jLDfZM2VMV3{8dSuT^lY|`my379z>LnBIgPbu%T4>NUDWu*3U<6(@)6i0!W#2jEfN*wy(Fj@rW'
    'PN(DPx6jvP=(MS2*y@E)%QP8oRS42Nz}i1<GD2!dc%E;PTu*3)yDjt{mELv+GBi=pZCu7fg5Sa?c;6wUn!YhX>A=M|W*@$@1|E}S'
    'kuk@W^+{UP!TW71jf?IJey@z|Od?DE2ESy`lR3*Oq&Sh%LD&$O8fo_mU~L2Mv=<RXbQ6Jr{-;vUU%%rqCvBj#W1)4qXohxq@V-6*'
    '!k*C@uLF_e5M{7C{$(P%@gP&tT3J0d`oCx$kI6+Ty_;nyhm)b_>x$eFli@^VSfUN?%=k?Y!XI4rqyerW$_WWB$mEu0@oOqlo^pAn'
    '<T(Fl^uP#-pM&X9Y|LoVNJ*#;-ps^@Dpd?0lTC!WE(h+4DziJ^Y=jG5F@4P0^=0*Ez8yOMK=fujf*MH_@`=l31o!XP9r^qVPVVto'
    'a0jYL7z5L%8(tX`tmukT*ILGPJCu{%qh;^5^5Pw>U^Oe(_$YIgC!U?y1mQWn2LQ{ZvZptFC+y(Zj-PT6AiX`u_Ies<%H)ctI+bUC'
    'mguNi@-1w7rCSk%HCk6g^c#-RSS;|mMeRM}S7aOV#Wd4bl_d}X0R0JepxpEKk0nRPVL11B+LC))tP}&s3u-kx4Yyq38g)kYDi}KX'
    'VL7aP&qz>PSK)UsKSJAnGH*PxIt9O!6=GRKIxNs1x>x;S%~bZni}zN_Hn!t%H52S3F|ght6T?}MYtMU8y93_2!AjLrEhk+rJzHrP'
    'JryoUU>&O>BwYLasM|b(Ab#FeSpb)lFwW!Fa{!XQWP@)=R~X9XJ8ROh6*WN;oQoK0a32=j44}V>xgfXWJd4ZZh4F{OQ`##L-NM)*'
    'x;;>#lp{E38T;q6?7@xGwUOJAIgyYQ^D=li8~}+qiYW&pY}fKWP_*_?M>f_!b3~f2#A^mKq&60XJ72E$Rk)Jmue*NKyv<3l|2i#z'
    '&)wRrx$`z8xbj*k=KyPe#=0yOcsoMEDuD^`7fwV!{Py*o*ik;BM7&32S#R(yv0|Hc&2lSDh=IjX19uoCRDlelq;6R&!0_71l4z^!'
    'fj}QouGG4Y#)rdEd9n~LrP9lEye?$seYXQ++%KFryk@XJ*`Eb9$MHQXamY;|i)GUBiJZ$5F>e-Qa<6r714&}!C~2pZYfkSy?>Ouh'
    '1nid6wmX;|hTlNqDQu3u??D$AfG|fU4;VsB*WC;~tD26|nS=@K{wP4q6TW`-EEzz4jD)YU1k;!}CKqv|Y9{aZ_1vngk!=p+C8Jg-'
    '!9x9T**gO(G_h+IK`@XcHNNb@5?&8U0?0e?cm-KfI}O0|vFrF}iEi+Vk0HZuo-X6<U=v5}5?vj4Fibh>$p6{cuE?**s#I8IZSUU?'
    'T7pA?UB)~Y0o8hLba-R<p4yo38c0y)2!NZ0`oJKTcs<}Sr2t526ayap$Q`veL1@P@0#8NXU38c<N_Xf7E2iCEUW<dbIjFZ%4wR-1'
    'BnDp=kr^!$zAFx1tc12d9dGo1Z5!0+-5Mqh;RL;*aM&yA_=H>O$}Q%<f8A7S+&SC+^2lw-gwMWQBIB5iNo!nmEYBN7%>Wmz$uPlP'
    'I<0Ah{!NC?z?WtLnH_J7DS^eQL-b>Psue^84)i{E>Ua!@_t{;I4Yl>-gh3_T)AQrk67gbyhMF4jap65UEjNeV*ECu5(trh=&YCCX'
    'XlIwZ>rQkw=P6}wBd!^()SUB5Ayd!l7)Lv?6tx(^t{`vYj)BoI_=N$638N1aOL9-jA6?(U69-_J&vmrk9wGM%Z?terqZFq;ciJ~f'
    '7psJL{@bRP97;mXDSuNz%=s~D5zx9b-=(k`X1+AdvK^wSST6jnMUYI7n=W*KIL&yngzF2)t=4!Iwr~p9Ct@}eHqU_h+o%&LelLEK'
    'MS4c`etZF}H;y+8E%R6j-O_@U`Sf8Cv|e%2i$}b_)emQZb@B!Sm*befYDup>8^3U{MGdxI1W8uB@m8r|{-wV%w4i023L5p*YwWdf'
    'fMHWjD(E(9d-ZIcvHhPNyWG<_WnLrQB$M=}<JYEm4y3V(kl3!`*C;M3Nob(4!-F&)KyxnmjN6$5sq>v-=~COch5ezgN#*~w%1xAz'
    'z>6QMude~#_l?*D&B6rEvj(=$KT*_Q%x!?@-$1YWDUZpg<Xu0kIvX|!l}dtrr10wMmFWbgO`AYqGk4Qu+0MTJT9G9F(7C@FX~OaF'
    'cfQY^GxI62Ea<cblI<t@6{Ry9g`hjfO*aq1+2Nbm6U<qedwp(n2p<TI7i+WB?B9uOsOery2Fz*SnUoEO!C<DcnTqL|2+AQl@^YYA'
    'W?!i-dIkF6FH3AVT&R2T9@LFUW}1&o%)@eO0zm`1mXG+3Bwrz7m^BAa^4{yb16Nw#*_qA$&$HbQ+Se&2qfxAWh*Sy5`p^`c!`3IP'
    'bQ;GRV1|rG>;^n*H%Y)?h2W!rY07{e#8V;7jf*xLjED>ng*iSRJLzjy&`g0Xkip-PWxgCIzLQCS21xZksb(mkUTD2Lg~Ade5`wlM'
    'relT+eClp-;iEI|v}fXlQxwq|{h-1W&hS9x?Md2f;y*%q>wX}`+N&RNN3w(iCW`^Pt6be%?$J}BN`|-vx^Zo@9O?x+>_8;0{Od2o'
    'y>3CR@=~UnbHCy{Q3E(%CDn`0OZ|Qmnt)4VBAMZOmE&#CA<e5jU!eDX82bBP8417=Cz{~?of$@da*-kjt9<wEDlk5<`^}2#KjsN`'
    'E;m-!j|0o!>prURkHnj=GDX)kN$1kfOS@0)fc4`Dx-WjQK_;%fHdwQpL5L3ffVH>vSA+}>j;%J=ZkahTIWVKlIvj`2QYR8`gavWB'
    'j5q}=YTEt4JWQs}cXsm2%ilE})2Bif+68rK<)LUwY9YDm!nmq=0xuf`!vP%G;PlytuH(ikyxbR9MGK7bl+LVw=twv}3IWh&R2_DW'
    '?tNGz16&uzIa)DJR_f`(lhX(w`&xGmZ&UR?iiqkzF_XMnvo8FuUJ1l5IThuQ&4^_bf?>T$dualTq??BQV#&6kJ+=O_Y;im#km09c'
    '&;}ad#p|V6Q|`HOW5O0%*E^zPBx(QE)5`sLh>hFjA(u4Vn$sdpQ`oSG3RuR@a#G>oT{@)|=tjkbX783yNRp?4q|ZJ~?pvLr)dh9k'
    'QWu(V0Hkfp3gy4Xg(>1cj@<fY#Lrryd)lnj<p;>ng>yhiZi+OW^kT4to5n(LavGMEr0nS39;U{QZqbSDxiSxb$JddEcmg)|7Z>N+'
    'Q{5Vi+?HpvB2}IZB;4(WwwNAAE#X{JrKzx~IKfL0EW_Dx*sY6)YbL!4VlvF3-PG;lJS#dIiNA9Wmc<P<2z$5*AwF~(c5Ekr$PuRq'
    'eBprgMD}1uR$I!AT0H2zptHaa99NYt{nJChLPY55l0@eoh21dFNBFr3Khr*Z+;eYg12X)(Yc7NTRc9N7*}E%I2$*a*r7mXsz|n*7'
    '`)d<Y_Y88*dOQ=zq#SOU!`epQL#Y!5H7ryx(^D>o?5B99{AuX$3+KI_R8E(26A>BnnA=K+v@Kv#0PV>uooab0Jav}%Z`D}4y4B+I'
    '@B)fbtl2bg#naAf?QtsCrd#{(C%1W~I$HMui>AcEGos?Oth7?9%&bXhF&6lnt3qSB;P+u;2`|zV)lFCco9&BV$r1dDZ{qsG-Zh!D'
    'HSRG?G{CZzS_Xx5&#@{DlPE}BEB9Os=NG5Byl)s1ohlY#XPn|*Y5dhvlE4Am3q30A63O6dVzK;QJMXDNyA`mg&U8$1VMiCUif-Q$'
    '2k_Wzw4{HyupVvxjTE=;z0>K6l2T<xTkMCA9D_qAIxk^SXu_Rn1putGkd`pmP`OBo6>(U}UeUmD506kkaRUlXJ!KLd$1ri&kx^_F'
    '1tY|<<x7%$>qeICC=hfu_o<K$u)74NNJgneyyNDVl88ozRFCL3VJy+t;NeO)q74~n?C+3rP|IA8%A~FxQ`65_=eD~WdE|`zQy4YG'
    '<W_DO;VuqvaJXG`pgImKE^cfLCy#*7JbF8fe70o5rShgstQ2Jj*;!p^5DF8RXbL>O7bwHP{XeEPq}GNhIj4}Cl2+1vH!59pGSYNB'
    'AgY2N{MR;FdRZP6KlnZMXDj1l-CV%bQt#1fHb;@&lEv*Y4sgJUVwv#Nbd~2^r3o}{2|$)C3Xrt$v2jl+4b{6r1bw;8$Xi=RY;Nn-'
    'QY0?3>bSo;HhDoqnmO(PMqWtRzM{+9dK8U{L$j$5Ta(gB^*Juxl2H8n<}buUWzQ#>8T*;_oS;7ugy(4r9`m+Q#=8V|==U%c(m>)7'
    'nu6u*^6;i&#AC>&YhA#n)0<7F2h|R?Aqy2<U}F+X<D!v9Aouh>1(UdUcbD;o=2F!N*fPoTZx~!`&70+#_s<(u3?A5N3Fg0T%Y?qa'
    'vJ#L}45}zY^D!EibD}^T82M!P`Zv~Wrl`xAY4FaDXcd&jaXQ(n36E(S#{2*t*8*bMDl`r{VV`KAW&bg(YTXq)sL#Qi@~%Ee_~;gI'
    '3?j+|hJz2H2yAB;si8w+`aPd6uj@bgN9PDSME$SGLZczx{SV>ZBrMJXEaIkcU!Zi>`%{Xm0^%Mt1D8{FvJet&1-erOlL$9+<)R|~'
    'laRSmwaSz!kXx*s>r`HAI`*aCtz47Dy2ki(!CIXI(B7Qt!c$%oSJ0niC<%QG0`KaLBVxIbi<3E(f_I4IE4^Xk^ps&u#Tw36rDk9r'
    'NxL%%!yG@*!p!qS&`$}kHg;QzY3JZ=ZN*E}A);!$Ojp(l32Ffk{A<g*qEMv%kpYs6s_alJ^e*)Nc-ha_d#N&&O2txX>d7gE$0ls3'
    '@0%Np-g^Ot?p0~hDkAm>)^tCqZkSpVXBZ!(GWv{6A@)V%CS;0kMy5PyuoO~cqj0_Y(g4*=fL1CO6bU21)P;j@DNjUolj->&dKb)%'
    '3?^B1HDG9f1iVxVw1cRsrY)3ihc&@r%s7)D-Q>Rjc85cDS2n}R*^ngKi7CT&W<w3@rbO;G5i*Fw^&E2PKB{%7FX|>IV7|c}mn16;'
    'V-?(-fqfQ-jmjfgXYnTR?UuUTD1ah4M>5YM<l3o(noZp3q0>ON$aYTv8;fS4&IC(_!g{X`B*hCU-R%xt=-JX5b=xM(?*EWDYq6%$'
    'x3HyL4DUVWerwl*;uq_Mu+C)MLDtTVF;$aHphr3?vY?VyI^Girn?P07_-%JlQg1GYYYJI8_DE}QKFfr9Yq2Lv@I~yb7%6~kT(`Y-'
    '7G2s>n=h70t{7}<yIqQxm6Tr`Pbv$#mYY3ZZhU}DO*hTGuE*MNYl^(%NFM1<`0(j87pU~vn6TrM%={j!OyboE^pY?A{{5wf{~=ZE'
    '{8}h5YQi5keWmw9EkYU-mGL*}po67B-8RAK8YQWvi-4nuFo~kzX@0GY0wohLSFz`}liylMJ@_PYDNp^3;qzjCqZ*IV8>^YRPG9~q'
    '&CdT^!W+BY>vN1}l<cP-3eZpSRF-!AP~;fhI@7Re8YgpA4M3Kxe#{)T`Npv<FPXsnDLTk^dBMc7fRZ4Pta@K9Jq1`yetCIV`v$Z!'
    'y~uxl=zMk7if+x*<v%pM$`bh;gWEOYG2E<alU3Hc90&23@66{cgOPrV--yREwGWUm<&Xe*!FL$nOA4}MCb2YenpU5LSCf@S>cGsM'
    'C}A?<AK3$8$A@?pMs(J;Ndz9@KJL+ieh4;zYCFG~@v^TV1eZ`(Nan~nE1SDP#N#pU;^&0gBYl24I-KxT2<F4LrlrEs6Ah`ytpsm#'
    'Y!g3hH9=dypLF_wKN8Bl{%;Y9EB&7j`jxx|_!bH>hdCTiGDB(3j!%yqzF*K#l+E_U;83m-o!fEWnYo(ccesdZ1ka6085S1{;9U2p'
    'mVt7;1}_v{gza(ijF->o9MC4yTBSk1<w!NNq@Hv<n?PbmRgE#%jHvpOO0HFCG|(m9L~`U<c$gQOb=`vcg?SjUhBritN^beJod>jk'
    'zR--@=aTLQ7@I)W1kEK29xt}GK$9dcjy^A%wW*RvN9Y>bbM<hrc{hmt`YU^fu8){espgBDqwt9|c7o;r%vj#8O$%y%GfaguEGpE0'
    'K^f13swj@uZjlz5&eV3`_OHXKe8Q(w4}`KtgzwaVve$^<$B`~~;*oG9Hy?4+qwVku0DgRii>9a>Y}NNyYMqADkUgvkX@y4taOFH('
    '>zy{chJi!n`(+=I+ihZZA^_2aD<PVv4oqQL5tou6fL2-iHetA+0F35hE*e=~5IGaOJm$%PUbs(!sKbQU2;*27i#Cp`+f0kX;%BvS'
    'WldmOuQx3KRsXx^vyF?PFz?-Po<MWPKq-3LD?&udQTnL#QyG=OIn5<7r4;|C#)983<>QnFA)nVmd^Tru+tW^S0MubB8%s<wPRAx7'
    '-mkyzGhdmY?<^d?^bt%bg3^b6^n!i-pQL&4H&rBk)sJuyiQdU4wtFe){(yDz|BEwUu;K~#RZXqQWeZ}8P=X9Af{>Ze*@0`i<v(JX'
    'k>n^UxXRYo;#7JHT0~1ive!0vGS~C=6K_U&pWW{Uz5$FS`3f#JZbwHl-Ni-*#D@{USBovHkmaC|wMi5^675l+kI|hVKhnt}<xR(7'
    '{V@u>N}VDdH@p;tGMgHc7p0R#;PVyqjM@l&nF_Jpo-+YMRQO%GKh3|ZNd8?fB3QsV4`!$Eyx!E&ecvODzm#%txR2h0?@+5qW2dvG'
    'zQKIp+szCS2mJ9JZ=xiS#C~zi?WOnPl#Rr!2Yo{()GK!hLKnZ?8ALdwRSmN2=4r{`8j5zjHDffwtZiKhRK>4GTsWRVUIDwGUC#CS'
    'n$(-48b8@2kC!efH{ya$AuymKT>um!@b0C)hink0>Gr#v|2%-whz+uw$P89;bX3GU{*YFyzUisW&#{UfLr99PFDmKm^Vxpo$H&~K'
    'P={;j7;?cfrOXnSi?EYzm@8~B@*(ZlvM9g%hcC1Er(CWNUO)Dg_Y80DN}N7aWIc#=Y7dk<f5hRhD4Of*+_nmhQ6~2}6?3jfJL=aU'
    '6-X7UNFThx<d4O)eAd>5_4--D?cQoxXUZV~paj!b4?|7?1<>gSex@)@=#;In{1Xlex#UTOzn;zJ?&3*2X7}4`Pxxg0Wc%kesn80g'
    '^E&&4iLh*peEPS7b|ING_3gEJnU@@BE{_*0YbV)qa3>jDBhY_>pfMk4Tz&LF>abMJZP3|wWd-%9w>(BSih(|(AcLU15oc*Rw`lxo'
    '!Zxt5-PjY%cEE6o2R!?6@cAcnyagz4)8oXuAN)46+9%rt&+s>CdXbKPgOzsm5%a)N`V)o>v=Uj0nUXzgs>8WAK{cv<xo5YAcJ@^A'
    'i?+0rC~~(`dB2f==F%USLVd;|#t^IdLDIJE8cMjnKF#3nd0(s6v{nCA(7gy&GIuhXfdU`<Mo7H#XlrO4>{cyNQ$INzP1$_0I!$9!'
    't6Q$_+ct+=r@PIe%w92=EJRX`OFxVJcJ9JP5JKaX4sR+Sb6mY*V)~NZJ9&u?39Hb@06zDG<TRxlMcIbOul!tG0*If^H8Q?5l%j>X'
    'pApJ>{B{%yOh|mt4U9$_-62Ej6tr@QTuQE|Q;Q0BY~^Qd8b#gM>`}b5ZBE5GrQAyWdECiw)oI$;!7qK|1%x6m=}6Jm9=rySc?q8o'
    'QA9b0p1mXl99QdSlEMeS3Q@8`MS^8~X~sR^%u)L_f8gq1SYy_$u8cODSJ{u{+u12Ig}xam)PDR!k<+9^5`*f#!ogqr0j8kardVsR'
    '-Z0-%{1PU@7_K<5E&D}wMe4zY0<|s+YnX5&bye^R;)ehVzS!ed;%JFScG>kptyk%X7ooF*eLLw*))m>;&9HLPaM09nCJEIhr7R@k'
    ')V>Um1guTEJ9X434ZN{y;~itg;R|&%)*>~@ly~;&zy-y`pw!ehkVXw&F+M8=1~p3=sSJ_t_P3qO?WJ?gym2dqzWpe%SxW<Bf)yW0'
    'KnV0q=l0rF!Fa|O6<{InP*;8qDA%z`$^8~A;vaP=);!T|@#_~_x>PKmaTmzJnBTaNFig3%1{}_sLD~^^ze#3TvqxGWwc16x?edRo'
    'o*Jd6U+%neG0aZ)t`-?}<g4s`xzw+mOjv`2nmcl!U!$*ecMUJFbL9kwG8<B}OAE7hDAxk72Z%Lv*^pYZ>87aGH1ms*Y#cEVqSiCk'
    'k30DPEnWw^2E!TUFvZx_T@ON6214FeTGp*kH|0#GokMhJ9%-`uIMtrt9Ks>^HI49so+({*vH|=U%3g4j(RqSq+&!d%s4lC7-FxpQ'
    'Xl?r6UM3oj&BAcL>|mKkhhcbDniCqUL-|iN=EoO!m%A;=LtU|I?^^i&%DD+*WEV!VHk>9GU&y**gCpZsyvnF8jjMKzC2!q>+T(}E'
    'LO)fnLW4K=a<_H`Z0mmn^?plrSw331xu5u)UHA8mB)(*Z%o*ft2By_73|?EIE#M`}s7Os~b*gk(o(xJU^1Rewsbye|+*I@jN?F7e'
    '4?PmC)q7RXBh&6#)k|5q%GZTiow1EVP$3E8Q<*uwr>u-ikQ{~gb)`v<&S%?`{_%-Gtt2Tno9$uCKjX(WWa*&dQ!Q+6nOu3S>Y=03'
    'dYxQg)iBfe15=tM+XcV}g#^k#NKpr&CctPG_s){Wy9K0X)K0JHh^$qRnsc0>zcQ_2=f9q6N;;_-d6cazAxbc+0<JvcStj$-b%+3)'
    'MhD9sf;IOS$ig;d+wCNCuF?2^IwT8kaDZhTfg@+QdoS?PzNsPiA>5NaeAM7T4g(14W9_>$e<_a1XPeilJGIW*0bpNO)}Q@j`dm5j'
    '==*>uWU9`0^@Yk}=(y;AtLL|`|0*;5PQ_zH2vd8kgxbAQQh>yeVvO>PcbI_x;-J1|V0{Ddf&QI^pP}jlaig!t)6d%2V&_A(kU|5y'
    'WiY0qkay6pAR`z;GaB&qP_9(L-u|@A1J~$7_up4z%vGbP_5@Xt-w!ULK&)CMI<c7eB#`yLM0zc^X(X`AY0aW03WG3SmM@3~ILoR2'
    '&nrb_$1o{oUIw|#Nbx^UB=g!iIIBF6-bD1;@iJJ~yL&8{C^q=g!KP$L9qpg5B-lq>fFqK|7}vxjYs+0$Pc9A4SwskVf?_c}4(&!R'
    '|I%VdKoAAamiw&^EbqZf_wnFnj*N?ONgYWQ2e2;FN)!e^f!}gM3QZw;g@%jS^6#dFr{!2V9X%_QFspfC`QLix5VhltL$^Hm`i%3*'
    'sH`n`Aa8=*9`W*GA+za85(7lpFc(h+Eb)mIYF*R;uOa_CD>!;WutbdJT71XflC)4Oa<V|nB&n#)v+0+>8|&%w*X4snx=`NUh70A^'
    'GFcn^0aguX7GM0@>6cSJGa8r`BX>lw;N3xx?lhpHT-0XYH){0K5`Dlq*Cx7&+c8<LVogq%DI;z$c;5j`j;MQjQP*Ewg}Q)Y)b41Y'
    '-29bnGJ7AmUuDO#hOe_l{Eq`z#&G_EtavqpfozJ4HJySBniMQSV$Ih=#ym-SXavV7EMED(OmBxV(^f&qsi&B1Qe_YE>#}vQx?_1)'
    '4b`exj?`KX1Namq!GjDlpKS<MPgbXx98eHV$nj4Zbu0Dp?wELw&Od|^M;Grdjbm=D`E_8%=($yaoT~YEu|J{t_#xs?+DtU#c!Xt6'
    '?$k^wf+lSope--Yy`>?n!#ELp7$AIHK{|V&RA*gVK$ERg(UySGr}f}K^3t4<u6wcx6vBho0JvBoO{c)O8KQE#<arO%!{LKW6?%`A'
    'uTuHQ`>2faoBIO>16=`NVitfjsD&vdan?tk_a@AJ^nR<FP<SF%1dVGyg}Ae6U%y$Wor9*-Ktv}logqaRVnN#XWoTckRkHu4W)MOn'
    'b-1^Zm-iG#5|QGlmiD?{g!f!r&XiCzmGDwh>DI^E0^>v^6C{j^ipAk|8<)x_^)1oNOKHvb;A8~xZZ@QZIluN*L&38j1{t`OAGV<u'
    'T-Cjf&nVq2NMB5ngnII(G7PJnXjA=hjz^KHj27=!E1dTj)x(;CBTy1}o<A}2$&0n#?J?kP-_v>kP0SGh%r7N6Gg8GEa%j>3rbF(@'
    'q?5><yFOm$&Y2!leIm&%+#5aKh<!cqvIT**!Q!<eODQmWq$KYUDS2jG-dI4q98{=Jky9x{Q77P6KLAB-g7*)>mr~-Hzhpb#xD5MG'
    'Y!IzTBNvB!ImS6UW6Xhc9Umqlr9}#l;zS3uY+3vLlvnj3Lm)#^Y&i6W8a@H~fM!~~SqZ<k#xGyQbdH03FgESkWj7*n6&?lviF=tB'
    'ZE&_0;l9g!#_r+n$+xmOl<p(_eJc@l$eRAHOrA$u2_>vDKOZ|xYm6IdQJ5oGKkUrq1x!(W+tGVQ)X*d=&n2RBti_6=qdSL!Jm&kO'
    'q`MVsEOvBDIpnY->ZgBL(kEQjjdEWw^=oWOX}{@O$#Sg?s6Iz9EKe}Bqka72&C&kapGbK+uqT2`fvJBgb$;$C>5w&u8+4boxqA)B'
    'E`d^r$D1l*#~+NnAN^l_Po3w@c3gedXete`q$yB;ZB6O^5=kfV^CX3w-sgEE!Y^Aw(J1+bo`ZcKpQcFwIMR+UhPweyS*L!fW4Bw_'
    'Z#ArdLUVAdbbf7e8A69rc%TDx&c^j$@su@rFy&Q2#TyUfx73Q)oH25dMX=;Xr$#FnV9x$8&X2$(ng(Z%nUId@N3Yy#a`5|PFIP=i'
    'l3}{~4mB?Q*U+k`jqy5!Aa-DaP@79Ua51!JxE+IzRy>Q3bM{#pKUZ8LO5DjMn{a|uaF$T?`du*w&&eeJa?E)|5BHl1geEh+T4&0&'
    '&kQ+Q=W)-j#qxF1o1z(ezdXiEH-MCz7Hcy;Y%DYdAk8CXd$IKF<w+>F?n>)@I^6kg8ujf|BGu@646t&s_tltT-uj+Eq53XcN$3C)'
    '@T7Ven4d@=o4&0+af^DXk=l=t4~FT~+-nrKG!TccTQU>ZkC@6dw=4I@yaYe5OP`O`%C^5R<ZZpi{5GV+p6|i;i-1CT5(_luJPYDw'
    '#s0w#7iXMD?LgbW1CI59EIaEhW^oKKJi~Gkzv9ck?h{_H9FX~yL5?I3ol=I(JkX-Im*X9~y$KMK>-3swSyegVC~O-8A!TIEF`~|G'
    'A&2T^STjcVc0Dm)XcJ`(aODYS##r8WhQLE?E9(4#`ocOYhKO>3svTim2R>AQy4^fJCFMv(c}iQ@n$u-U?ts#pn&j(keZ1nejfFBI'
    'KegIN#nz{!^O+jW2Te`+fVYV5^e@=MY&P_5**9i`r4mS8lpFZQt+7nDuY_%f<4*kuyM+j9Uo4>hTsc%#?E$_C#n5Y#i=~}&&+K(r'
    '1`eH2X)9(I$;Uw7LPQXbA4Wx-PL+y5$nhBDl=)}e0tqceX}a*P88rmv!2lSA&Ph8O$fTeW>wAP2a39!uiA8inGTCd(Z>CfCW)G~4'
    'V5M<|!l31Cf8%70pGb^s#Vkz-t9wHA`15lgY!jWhInyuF!^KwpeN{Gb3q0gLGV@wYp&@T!iqqo-(qKyaDgkDDm%%hf4z<xf7ci#H'
    'P4w)u3j5&e?+{CnRw{sbJ85=Sn1KAtmN`-DUy%2QeO?q-S<IDPe)r3QQWs8X9&e0aN-GWNeSnK)y4FN9w>A5g70#b7|4Km?kZDUT'
    '&r=r57NH>MnSQpLw}>}d(e3A7O4QP1qfDkYkoztso`wU)HRRZNyKi~B2RypT7}LO9vt7vRgl5B{dT!U#{mn8I^9cLJ$uda5b`CwG'
    'B$wiK>tBQd0<v%UsN*f@6t><bYjdm<R?NklcuwQ?Jd09<NdKk1+qz%Lf8q63{!lb!>5~Q#H7e1LAT1g^!aw^oyC(E@`}7RZSDa7}'
    'pTp!Y66TbT;TUoeO|d1C{Ok@i`Ql!Ff^q^%!M#jZ>sz{xRoSgA>2k>dIQWe$!D$=&=zeM;v_ea%t1?v4DA=^Daz#F4h;MB+56&qO'
    'I(Uz2B>p1v?h%{2d2$$&8FrSfqsBd8iKWF>r!t5h{A4zs`?n^r_%x#pcwuI73;ZqUXYGvAfmBDio}qTQ!;vvc-Y5;eOczpS0E3p{'
    '3$CdH_|hFf4KliHXRX_1BxNjO<*Plre0_6k9b{9((1w@@cA3L|<&~DGq`^H6@<x(xsxL2&^JOZ1F<jAc(O?^h*!7wFUIy9wN<@y%'
    'm^&4PV^mb3>1Y|VLdU$5BR^!vkKTW3ub!KYeDP+XaF2ZZm<ZzSDclA%p9!Zoh}Ltu$YRKMPByG5UB=Pyw|Qv8kw4*;s8@+Yijg%G'
    'AiJTENC>@KL}lvt>Iy=_%5sfYOsrXPQWQ)u!@P*?7$iSDD6sh-r_ESw&Hb*FP)=%s!cur26IYUGIY6e|mfLp83lK?bXFv#c^fV5Q'
    'N0hzakjbJXN@ow8#4}}Hb+RRQF8@0=kid-Frf`VN>|u-G+Ep^#b~5`!ggVXvcAaRmmS?ogeJBbsl4a;$8!A%$3?#bs>)JPxQF|b?'
    'k@~fW-*`Xip(wf9iF@X->}J4-d3LJd@a*-a9G`f<b1eb18?D3M$a?_{y>*y=no|o0qO_U2Imc+ZfEn6NMugU7yPtK-nUUX|WGMG('
    '_Uo4!sOMdd<ZlItt!}DtAMUx-4|@4mDRKUUMW<3*UmRHFO@$N0Fe!jJpvIky_hDq%9n7tc#iG?;oq<FV(#&)GY=E`bWHS1*?#Y9<'
    '0V8mE)v`@pSW3@P5H0!3Tu%VdS8ea8n!CvU8JQXWH=1iQ<2$qg=$!{FVL|<;Oo6|{N6RMM-S1XBIUlf}pF~edKUg|G<WXaPO?7t#'
    '4rVu9r`DJv;0ia`GTl)>`gy7R`_b*$O4hM${i1Urk1v6B6hSD*=$CPFdLA`(Q;r(vh4=^7!Ai5T`lk`u2`dZ21w=B|)wMpY=Z)tc'
    '?{r?-C2`yz?h6n;=27dYFCX0H0gFCSxwWAOzt<QS_VFY>*LbZby$cZ1HZWO_%Y=A+;ZgTo-erAu>eoV<9}Q=1E-KI>tMro~HmqIE'
    '<<;yrEy$+>@I_1Zi3~U0^CIdZHBlC{<tJ#=0>z34t{TX*Ir2#tiYLrb5aT}_IehL!;X#jglI4>@ibltU^#plq7@9s)eNYKGhL#sK'
    'g*ECoFjm=-#Z7dDaw7J?!0weFl$|GHehsmvG-Vbk>w%(NJxj6DLK7Y&YR=xDwL&e1>I2fx8F%MPG=N=vGYzP0gW=z39=(-i{*;H='
    '$K%K)HJ9J#1hwG3FjTW6Dg#JGiyP+4K;t|JI}tUb`4s0C^E$bF*vO&2=CpH5$o+pe%24`<5#U975a?^?QYh~HIJ~E==&rEz{Ik=Z'
    'r5+N%I>{cYZ44)Q!7;kHLE=EsHvTzC5TCL8&p4{1%Bp_IVq^BzyPFG?1JIG}JtP*gcf#_15c)?y0#4iJ@hqvtW0;1V@|y~P!^1L}'
    '%RD0M!4PDQK5_UkakQkdn|Y=ZY-mU~sv#!zd5Fx9hu@A@M-l#YXq7}!M<f+~M6X}b?2jAd+Yj%tL@mrYKpk~Dk{vg<@`2j=j~W)c'
    '9gaS_(#M@SwbMgQI!b+Cra^5yOX<OEygQ55*pTQ(BtXaCN(-3Gm6B#$JN9S{4yNTq6a7;}8D+wVVS7net`fc>Wi6$?Jk4TzHd1tb'
    'S+hx;=3!atDJ}#~{wR>);g*4Ki-d*LUnlj8<Tl3c(_8n0War1Qm9nHSi1CWET!xo3i6#0*hOe>D9;@YX*YlOD)wN@HETWkDNm6@%'
    'd@K=bSl+o;lBCL%mZZs9e>i!2)9Nd*2=0Qj1pTs9|5OTF3{-ppdd$Ek;wgrAF&ELUaG7{!!P0eMU<4i6D?#8K?_n^$yRpah(~w<4'
    'ftx5WT(j(fd_H<rMUlDTqDOYD3C3{`%G(>xG|wL-<kg)@Y|K7<CK!kwq4nf6#0;`;+q{>Zpw2{d?pr{=>#XEm^smHAx9U!fpmVf;'
    'oc19?3up~te4hqgjI!&a67_c1I~HE7Uj6V|PO!-9;z7EjRg1V%$dB{@jQ$xQT3^S-rG5-pQ`pNrj^Cq=fkec-#*?SwWPC{&MKS&V'
    '!A8|YAOQ~=b?TfEuNe$7UXoLcU^;r07L&qg$8<ro#6N@}7n=C#!ehC>5@@f8{fk2c{(iR33NY3msxNavU<1RGFd<!N`C%H(TlTep'
    'R9_uePQx-zv!_>dF@7P|Cf<R@j=zE`U+tO&sz9P;Qt5#8OF$hcBiP&0jqc`N*1PO`4JATXn+aUjCf7SJwd@fgtrpQ-ZcedcFJuKk'
    'KYqFzQ349q9_RKF_;qffHkV*yS)7V^a#+pm2SJLlsjPo**v0e*NJN55)CzZ|c)oVtOwMAKYnc90KfA1OqK%m?Gvo2c*QY#Ac()Bt'
    'QNNUA^lmq8_^07}E!H6G)rZg+j`CM7l`s(KtH|gwq#*Fe{qFrNy_FqWUZh`$NIoq;QjfuxNvi!?7zPR9u^CI2=_4}FjiwFB8Z}pi'
    'oV_{1=WyaIH-!qFt3XMEL#V7u&Hiwn#I&iWbGKP<i3&$rl$j<hZ@#Jvjtk>_KOB209W#bl1NQm{l5>wn&_@LvTF-vpWaO<MDG&eW'
    '^iu;2z)?CqyKZxqP+9_SPu4|Idx%fY-CEh}?eEI!We4$J3Y`A9Yuy>*U6iIO4&m`B^v6x`w0qR@`{1^F+p#LV3IQ<8-FPrN=m?w4'
    'gF!?pfh$IFe^t=|>Yzi8-aCyqf){VP5`tRVhogfV;~-(C!MnH!)++JQTjrBpE&vya^F8?ihV;jM!)CGn{}SY;;nkaP`%lU4YC1g4'
    '<#ZIK&G%7LjVaP*B0~_NZSw#UId)WL@_}3pQen^bsOlF05w3~P+4v^TsY{Z%;IsiRen~6$%!Z+ogX>kC#WBT%?lprcKR9c4RW`;@'
    'vQonsZ)nfJK%@Lr?CIe&3`b(3D5p#{AwF5oC7Tf4y2}eHF#(AwuA^UllJpZ5F*{f3u{6;sI>`I_Z__>wO`f5ayGE61Cz~Zj+YqEU'
    'Z`VFT3KU}@jlW{11!HA9c-_iHyv;*joyPaKgY+zy9l0VIt@s2x3;J8(1+F*y2{mO!kf||C6hCR*cm+=i@yVKez2yqHy?(cV?J*qc'
    'hHD~<0VIwBb@MXKF($+4snd&<k1<lX)f|%AJWs%hX1sOGIQ}@ArCa7LOq=oF82EEISEU!s-g`9l!=QiNJNIW7Zsad}=tVHxv2SCK'
    'Zs@nelT>Hs%55H@W3*#od_mE_w0$a+GD`$#u^@|F(`Q!8FS;d>5z{;KCBrgE>fHmczSpq=qR4`iTeZYQn2y!=c1J*49#n=fP>$*J'
    '4-?e*oCxHk^19kFL^IOse8R=H-ADUdp$nwDyT4%-B1lzf&WOMD<|O5BdhvSZtps8=*F_6k4HM1I@+#z^3x(-!pc!)6cFffTqlY`('
    'kT}m>h>@#R40q+bpwu*?WFU^mE%vN?g;D#UiR7h-#woPLo<Xisi72&HkQ!$DO$Tf4C?$05H!w&$OI_cvj|6>cM>X6_j;{6%g0s{u'
    '!mOS_9H2*Csu%u)E;iqfeQ+gIx`P>Dj&6ARdLa`%4@9`!u5x#nVF+8rQ*iIDSccL;n*EEZ7P8XQ4r)ug8K<R8FoCI`#lOc3@Cs)_'
    'yLgV~WQM_eYKDy}Gkf2D_s7%Ul>u6E#CD3hdJ%yTUoYJ#?|p;kDD*!CG?r0uCFZl--EN<IS6#BcH&-+W=V=}Vv2+P))An$O6n1L}'
    '*fA^;HR=Y?z+)t@jgK;qHqcfOE`%+0r+U4~IIBRNMGws*3fVf!+wh`S^LXaJb((XKAcb}LoVl-t$Fse=4BV~Wz$rsKuD%zUmC#fo'
    'h#iUGEIC2)vhf_to;><zvI#|;iQLnp{Xj$;>?${k;n4TY2^p(qlMouBc=?V81^42>KWD@TVAi=r6Uv&4L-NP>vN1@W!UDjHlox}-'
    '_!i|zT?l2^(h|DzZdO_O=X3g<zFgFC*67v*|DQUO+7^9Q8j0~%eNW5Wq4aYKpNk`wCUZ__bcTO460nD7iS5u&qt-xGU)6#kN+`dt'
    'g2T&K6MQ8SZXRl%T93N@j%m!5T-p@-&Bv5bT|=~a+a~}mB`$JyN4QYJ|GQs5H*^_#y)ezly9xFRtU*6b8Sh4(^^6>a4l1rSZbyiL'
    'FV1=4k}&ia1_5Ee|Fvxar-F8MGPpS-TjttQk#XDO#YynF0&(qg-oI_N`X2qYN(3<T529MQ<^a_R6mGe4KYNnWPV__D2Z8~tEg_)a'
    'zRb!_`qAS@6)v99@p5S>;L+y0T?st)gPNGUXaU|n>=Rn#(Lv9Fe^&VB;v;b!;adiU-P@4vg)ZntxealwuY%!&S?wNh;;sRxeRCI~'
    'N{Fl~WpH__Fn3qqAQ_hFAc{Ot&$Uvm7;TJR(rgV`FHDp?pG5#`?L{HYIp=*4y$~HiF4N1b-XekZP6{bfk5{}I0p=(pOf~vr-2!rb'
    'hYin)2SaYlU*Ig{Pl(OVM;HUI@?tisC(t5`Y9|LoA`*tKcX~p269$=|_4PMi`^_I=>bgZS%e{5gvJJx2FvtfpD~+7I47hOM4uN5h'
    'z^b2}B~n)($t!o-OUcAWW-0i^PJewi4H#M>Cf5jf7X+2vVIped?i9V?cK`p|-e+4^I1>F^uFj|dtY}d5gzx^i`-m03YF6(H&fTyN'
    'iDLcmLgWN^p+rB{ZlJn?<@w4uMq6;*0$Wgz1@tVkW;2&T=Di@CLDNH!Szzx;tfb_p1;|=xF{gtTYD&vaPwDBhC~7)6%emTJ$|v%B'
    'z9TRB{Y;VO7DBs&M2i}bHbH>IbQiB>zrT_<SZCqlRF7E$A_YHMKx<$BkxArU`Z_)-V&rgWC^hGvl^M;+&l+P}2DC=tOu1JSh-Wgx'
    '#GHTC+L#JeI>6+9IKLx&*!O*4(9&ktFI^Y$`V(}qnn`dGURoSt8yN&&8EV**)Gq}YT|s20JV|i;fd@Y+PpFAX&9R>P0hrWLY0&u#'
    'c2^;wc2)uLGk_ivla#;T{LOCRndyBDEl+EhAWiSgLrY#~M{h-^Ao!Tt+iv1{jt>+vDW10A!k_mwQ6zA)z2Pf+4JW=em2>}OpLD4%'
    ';wmD!E*IC9843!4fTWvE>lTwZVB27|W+5O3Iu5+KgG8vP4d6lml~@kPYy#lRcGyy1*~+t|Z!U|b96k+KJ4BVQ_PFZL3>VHFAo1%<'
    'Vmp|mWt>;ZX|r?IkYjWt*xj5FCPt1~_$%1j_Ngsi!f_%5kMgbk%SE2`dr**a1M{@qSHpWjq;Ircdgom+i!MEJs)~WpLI&Aor}*WK'
    'qmNnu7<3;EA88O?$&{6VzLFqdW!KZ~LoJ%POG~GACnW`1j|27N>S`BGQ`TVJ^zV!iy;h56A_Fi-WqcFgZ6Q}6r#RzzpM(HH`J;u3'
    'JIGs$V#JmhLVcWMBa0t!=KdsunaRehN%E~-6icv-F0bT}qnOH;va@4@^Gcth_gS7AkzsMmup?;P57=^Bp|KAe`2a4QcfiR~1iBt|'
    'D+_oXW$W0}?m3SGG0($pi3zk$VU`@-Cu_rG05U9yh8H77uU01*q_uGfeE8fgQ9K-aRa~j`zA0Ois$t|mOly*Yu$tc_h3reE5}4X`'
    '1LNxyb>LGBtLP4Y^&9;@5#1>|6w}>8a9sWpZ540NXZ}B_J@t|;g0@d3Q8D_oi*6U4WIqb2e696s1$V%rLd)5Y+FK_}v?Cz2=?^kw'
    '`LX*8_*l>IJ!yK3$Qz$0+ux$9TYF{LJJ5wR;NwS(r)l_rz&ewUb_vSQ6=St4;A_!OzqyWQk_!Zy>a_XL5+{l0N&#YP$3I9IB|F_+'
    'gRkCsP8|ppx3b+_lm9ON1W;5>DAJ%lD}E`mxM13Q`{5eC*lyyAxI-Kl$N;aL0b?m_@#i?fCGwE}dYEr@TTBHEn?S_d7lu1?*P0MG'
    '=3<x7Y~`At#P66LQm2yyIP_CU|G??K>foMw{SgU}(ouak*<&ipg9&_M%nz&<%l|x9U)pQ4ps_RU`_c`>)zxg6O}<79#t2L<VoWB*'
    '5MAS<665%&nt=Q}kD?8d#_)7WllW56HIHEg&2uGrqOjk3k`O*7K0Gdl8%r8@(CG$wtAivtQe#Xk1C;mmxSEZIjCl%UAEIt`P|4gn'
    '?D#GF$bx%?i8#qwo^`-0b<R{DlmvR-4pgGfS%3m`!eDsSy46d6Gy1r_&x*>=|BPk^nMrVWvLe+mteIacaYenmV_VX&(oM%Z^E8K1'
    'a`6+hCixt3V8xumUHTV;oR$*kTB0UD`xdyQ>j2M9a1r>V@1UHvurdmT`5U;?iM-?0`>4{2mKiVh;P#2GMU|$QCrX~KwNudTwBG}Q'
    'E*|FiyR-19d-dB+9JHBUNEVbX2X52Ao;Obu9<vhD>Fj(#nbh(5j(31%FX>`ppeYL(XvSVg-!hwMKXS7;%5|fak@xM}6yPO=C(X-u'
    'H-GWT1yc?PM}-`GYYY41+(NmL(Ut@RZ2aUIqP-A)`!?T5&rq?Aone^Z>Ay&LvRujpYXc)#5eQ|sGWZ9NSf#+e_NMtX(=V<-O~3RT'
    'N-sqPF$f>df7kriS?LqhBv;dK^&?i_4KRxXX$*!7QACZ5UtjbCzr{i{S{A0Kcg#MuF7knG1`~4-WG?G3IerA_h2`xhEB7XANScDC'
    'r$;K_-`|6h@HBxWh&+i{L|+A##6RiJMdXj11A$8PX$?}Zi%h{#hM43X4k70yV<wDib2MI1F>ya6#x-|CwiD-o`{wL8TmZc=z3^Xi'
    'Ll7&$2b@Rq<j?8^Uk}9K(N~1fWC8Qol&ZujMfG&=T`~<6e_}87{^??OmlVW!l#8X7IyZ*pY78_SLVYF_t#4ac`<`)kV!=v<L=Qjp'
    'X4ZB>)*NvL3krgsbgbbEXwOc9d7<iMcQ~<?nK6_$ju$mU4eWi(*%d}{1e8`4(iPm1*tuQ;)s7TEbJ+n9Xwy%fz|-k4=D3S)I?~xG'
    '|C}UAiF6aBUI@gll9j4q#&*VL^K}llMoj0Z4&l1igsXQ*CLOp~YfAewPqe0S?qaEmB-jW0ti>t`7o_TT+jgTT2*@rSCdxD<2bD*e'
    '`&xPIB1j2fp(qFvrms2e>|!ZvW$i2*A%YDnB^&f9%%lA7EBI!%YA&L)9V6fBJ1h=&i;`=x;|RCG`Py_>zBoja(rzR~BxT(IsEriu'
    '#2OXb{}nz^CIZG!k%=WMqb|Z8{EpqbVZw@{D5Hroi(W&fue0AymFiES12qNt0PT!Rwy_!YDn<dj7q~t_e{Iw5s#D$HI`2?3Aq6HD'
    'k8N1|RKnxdh|+aS<G!RZA+cmY1R{=qp{OMzJJl5BboM2_o%FfmO!n3NXnQ~=Mf$45Wt?yE4}fb}o)b;q{}k-Gi%j?L8JiRu;qa4D'
    '^&|E2cOY2F961ah+SQO}F)CwyCHw_z(igjxJHjWij7i@i1y{|yGGL@?46|1Ut7`zyJkAmEc)+PY#eNw_0eGZ;scd%J+Ah%Nvtr-$'
    'phnM8dM$i+Pxc_>XT$3Y#D;1p)+7QATN75dA?2~){*_ho7XcC;`%_^^a&x3GXC4zVQQwczgiK=oxzTh{M<%|@d8J%|@7h(fS#iEq'
    '5T?|XiPt3n;E{6JJ)=h?@h3@zJbl>UW(?ga^y^`B+zka0EmTr`xkV`{Z9!zCIhVZ3#wT6|HDjMxf}j&Y5*|5thYTa$+nn%pbYd})'
    'zmv?3n|nXOz777~-|ek?yKY}seYom;Qyi~ZJ3p*+SF5|H5J{Dz>LW;06mIInMswEWfsb6;u&_Zn$Nfd2!}Kjck0070T=F1fz5Sa`'
    '3PL;^yUAee$*Hkd5B&jT^F9IpT(BfR6{$^7w7~~Hzfjml+a!zJ%c~`>d<IKgGJ$}iS=a$rVA3`WWMVSzGFtOcLG=u#j-WKJJ<9<5'
    'v6K&P9gTJbP+rEa+a3$v1h_Ag1&?OW%&as`#*&LZ0JKkZ^Sy{nlPk+=8pGfOA`&EAXqm45WZgn1{v<(#s8DMfjyJYq=+OT;4`tXz'
    'Py&iUI5FC6nNIqAX5So8tyu!xnWk^1a&jiw>Qq<Hh^q~5yhOgiFP=JknBBdukTbAR@Yyqrqc!F~aFTQ0@x4;fO!>hIfHEZ3vK~;Z'
    '@nwUB{#teyi(M^J^9(t(qh!8x*dN)r-wk95!sLg9E-lFGAOU)p!k~BNDg@Mg(<e5Yt^cD8X{Z*x8qC^#+@b}Fg>|@uBD1plf#Vpm'
    'UNpvyv<|6gTT3K-?{}`@)3<UrRF)k!Gn~Qe(c@-s_S^aR2+2$1o&OI)+{#t$e~+wiJvWH`GG$}Kj}QxMyhhdPh4s@k-|}X=FgWPi'
    '<G{_KY`Kh<gm%KG)7XvWs<^;Oq1ZDHq^Aamwu5yI)9BS~b|nm9e>xhwVr_I_l@$HjCD=;`Kn(yPWEM>r&em#=&hc(_@M%DC_u^WS'
    'yR4{=32^U`py@oGHXv%Vcjv3nMQ<}B@2+<ikU#U%yQ=9l5$znQ@g{^iWB4Q9guuBw`%)f~*>>(Cqb7fEiNUtIpJ(RtMx&r_K;a*F'
    '2&xR>#&P_w$MD@L607Dp9dfk$cQf1AP$1D=?u7Ib|B@B~Ktm17fJFj7Y0uQps{!f&`m_m8%fZ_dDHVbgVqYy$dj!%4qxPW#=O@l*'
    'Kdi=pW-x~35gdE51dE92e8ic{3RW6CYOupWgaY>n;wi@a(L(?bp$*DD*~YWyEY`;&^M4;NBOtmFDsA|YrNmL)9zp^yVyYXl+c^$v'
    '%nrM$hzks^KLq1e;}pB>7{j=k@)jPw$;#e>^vO6*h_1@+knE62ehyC_uP|$$%jKFSB$+L)S3k7WP&;Mea<GNHb=xQ@Wy>?P=B=#='
    'vg#I%;IXX&?Y@@vGwNPU63$mDjoqSR^1^8n7G@o(!in2J4#-v|G(hKGnRm=pb$dmA`H{?$LfXHpku3Oh$7g>brA;Uz-!vmGv{!A^'
    'gZ#!(onpUNlDVWojIXTq;l^m6r*i<WI0JLhZKa;KlRjgHl?T?kcaRMWgd$xU%DZ^=-u+~}NwX=UU9+P5l=2J9$wHG_8V<rmxrE!*'
    '3dr^m2I?$@owPcB^sUveq-=KH9gl=(u|dV}=UP9lr^RJZY+{~@rx6ru!D~y+aUDA%uDO-xKP?-Wx@)3E#JTW8Im%eNRD?hHxO0=1'
    'PKF(4aAl*V^NOKYV8co|A*E7=E-wm{l5narTS>x8R!QCa;;fGkJR<hb-J>i~k`IM=nJhjG>cz6QENjk@WY8r+a^h0SN>D?OJ58#B'
    ')UN|8KPOBrUtTS3a1!jj`Ir4CD1hG<SYpn0CBN{rW%}reayk(HvagI-rUha1e)UAM%QEXhBSi=K2~FM73V%#%F%a#M?Nw}P5HB>h'
    'EsA%cqGJPrwP=SG8C90EtJ<BN&bms^t!f7&auRopessv+A0*oxB4WOzQ;p0^vgqZ-K$gq4$c!dc31kc*^w*jqM^_%XL`diG+OqyX'
    'iZD*ICd*U?Yg|LP->$mYicEoU*_ROPCl61_>t)LiqbK@&&GHnSv|_IR0(iHF00(CxBM@2QX*7X#v1zcq=b)RVoRij`EQ4Q>Z1eqR'
    '`AdbRNfgxEi58FFZ>=Cu{9Q}4Tl8w+X~6qh?KC=uI_91)sf31;_arX{Op6$h0aa|{w;mn&CI=*QV3C(N6`YFR_L~^SLCm2#ScGWx'
    'R0>CHl?Z533TL_;e8Fd9-m<zBg(QSoz*7AtCP8O=;BhZhXGaJ~ycmxoUcP%SwG)E(78|1+=YD%dS-AFFdj;<BkYYfJpZCR4-9ab$'
    '9KqJ@qtrqN0g-A6BU6F7&G)$ya+dFj*FAg5fX>_<noGMn0`|WYxVIvc=!%2<GAD!UfDl6Wo^thlDz<fhLP}f&Nu}ignW*QWKU1z)'
    '_;6vHS9Gqs^SDUE526KR6e^ZdHz~UM#e?}_aKcjN{OSU8b(N$q2#?T3&$Vg0@G+GHYPD(3P2lrB<-5rv=)|R%+-Yv4we#qu6;@NZ'
    '{XF7$k!PQYP^BlfHM^+A^~WinWPf`CW^zsg61&4-wX&iIV??1GNY9?Ei2wTkBA-?N4|ThKNn>_6Bl4CqjVn&4P(1z~{H?j`Nd;7X'
    'iC#VhX%!sz2u;u8_a;K=RV0;UXOkh1;LJtlh+TMU>>(|HdE>kUv_iq{^!}F>a02byA72=nL|Awnh%zxTb0eJm0R7-UPBs&Pp*WaG'
    ';ptgDROMkF0;<#aI)S(yQM0ebV{nN}B4g@x56}V_`!QOPfuk}6HZ9dx9m`Sg-4%@Q-~&x><pkjmbBaaW^T8R1cN%QHh!HK^zZIGL'
    'O3?6_3xaTE++`X~3H@6JttB>@t=cY}%p{0KBI9Qow)%txtX&i1BLzjcp&5S9UAXP|uOfn~h2B=J&tdKB9#CkzKf)hbqb4A8TY|%x'
    'fweD)ay&c_-2WP6&t}FL+P9N=4IwA5thb#uC7+J85H8n#rV^bQtZeG&w4?9HgDGnvPf_6K$Mzx$NiV%gu=xXX->HV0a4#7(b;UI9'
    'P~|jpG%%?QAtoYHhb6jV+mBN9QwcB3Lbc!gRoj37#(G;-Z#iDEc+hDj)2}FSjrRGQ3C`K@`ZS)QOn#=6{UK;Qke3(zFt2sYPB<s{'
    '4t)}yWQ380dRZ$?G&Rv|mS*|c2_qD1%t84&cjl1<s@iB91x{7-feEnTL8o!I8ZrUw+iZr5a69EX!yanZ1$fO@zt>zkznVlb19PJz'
    'T>PEZ=rM(r9*K^faB&`nems`kjZ94Rm!`LsejgGX6v{1?UubOb$*6`hI1Ey)ryRx`3M%Tp;9@Fs@-K2SrEO<MHcRdfJkIQ9aNmh}'
    'E<W`%yo|?F(o0aP_1kpQQZ5p`1jp_PA6P(=N^E`;nJ+Rhfs8Ll(qWFmX-Kn&s}~n}R1-BZ^M~2`$C1&yXj4xrirv63)reBEKRlF<'
    'jY}tR%jr}L8qRErcl=(&jqvi&%}YJMF61PIaP|CHC@KwQ8LdI5t)SzQz^eL(i#_l86y`S^wN)c6@rD?fZ^ugcireonF$pYv!=#3L'
    'sikMu0SA7-J-Hae-+TvQ4FSM100HaF(mck#uOE}v3kmQvm>mPTT8Lgcn>qUbe+oTvq+Kdv;DxYoR<-Du4ku~}@K!V0q0g=5#ZLH='
    '1ix$R8P2fawkFu=+4(isIJP6;?P9s;ham=C-$Yr;+g$LUg}}`m-dvd8#$y#aweWIzk<vxqe@3I#kcl+!?9v-fCUBH=zwBNlies8R'
    'u#!5e++8k-Bfo5$&0}089BgREX<~z{A9Q-r%9)(9bC&bu6XA{e+NfHKY<|AhWHHnJ?e)XRB^Z#b8+gK<x@O0pvL%)nIqG{jJCELO'
    '#;6$amI5(E7#PK$P?!TgxxTuT{XJlY2L#G1gwdoZn&E&U+IHPwkgKRm9EIB5-nbMgMJHchjAx-3vBz^Ju<FZ^_!JILhFahaN(KN-'
    'y?Q<kNS}}YJIMf}pGF+4A;4o8=$cm11mc&5CsIW|wOZ<Mq4h}oMy${<kYANK6lJT?r)WAyyP`Q;5=M>>4Z{_k5A1+CB_gQ0lAW%H'
    'LZ%%50nTtcg=L7*)L)UiotB{qNf8!~5%HMbA?_gp#@2NrHOw1omCkpx<1!V-v(F$KX3~S#j(Pa3#p#sN#)X^^AyjD=_UiVtuOeNr'
    'gQM|eD+O@t2!CNp`VmP$PbFt%U-`l9OoNn3)3m4k2gSlI9-~twc7H0AhatSET{iB&K{Q+;!Q+>2BS!bf6&+AbG@#;;RBK&}eWr&~'
    'Mp8o=9rGfocA@s!?azk{O&P%z%&o3TNg<{czJFD;cBBB;jbB{KO$wXagtsYYnWP_4ijN3Bi+@DarR&Fr2{l@pUoUvSA#FmtQ$bCL'
    '%~zH1h*&5x1VT%TI*}kvTzWZEt<Fc}{G@UtJPev-L4a)k<eDs)z+JT+?(L*sVA){Sc>}YUAPcc@Jnz&wztl=|JPUW$GYj>u?Vy=8'
    '<Q%*;c-qJA>TZ4{>&^`Bg0~?6ldr_#YM%djzVVHgB~?~`6eRB@p>rFWaUUx!O?-CZt3h*4pj|RFIPsa>HR9T)8~n6z2XhRpP}ni8'
    '18r7VPN=c^cnA!W&PVmSRwRtM90i<8$FuJtxaa!I&OzL7a=CS_TxA|f7GJ*U=m>d2te2&L*Doj;OuBy+gH{7a%%q)~z)Wa$wLa-w'
    '^}N$1@zrz6uc+U?BVUSIGA@j1l%W8*W`oTAPDXiLmGN(D$pX7aYz&he=PfAj1Tn!7O}OAPqKn|?PqUky8uVZ7N>yE#%Ek3UKd`oD'
    'j4Q00kYttcI5`ab(sf62kp7cL(U_WINpYM}K3)O_3W#_&PSrg89yr!Rw|$Lr7Yb2+!8p2%1WAUWkDu5J5BmCTSXI!R76&m%nBNZK'
    'P?CvqzD|`jrUy*0iAL3w3{1$IjvCW~s-C59QSQmNiF-_Ist=GF9@5=$H9B5=XLd$eFhIyidezVrcVf={re6$RtW-x)&l3(I9a?@W'
    '1DqtJnBKHvn-nA?Go`&9puzuv={E^e`K<XLv_a&z6shT|tt&Fv^`)Yy;DM&D#c_h3ZJz7eZ(9RfCnNs=P~Auxov3W;K-n+~a;;;C'
    'rinGLx3^V_`3^O=X%Nf_*Wog2<DEY-AD`a@ZSSkrU&qVniCdU$s|=EDJvK-XMu*DXZ)=1#%86x#{sGcV!4Gq!lrzZ&n7VvIRK)C6'
    'v;uL0qfm93UWU~3A6Y13%?h->PzTYp;*t|qiQce(nKs__sqBtM5szWOBm-IYAEnbZA4`KSF6H$5G1(zbHovh!&TMGuFK4U{2q=61'
    '+K=`;9C}d-8q+Kmt`;dSC|ya>(jnhDMIyb(1$%iRtKba<$fmE#NxiL(TQ^U_mxS&={q1ebyi(&_5G*tvw{b=Rm~#eaG!bxN2tF_U'
    '&d~h0$Hm$KBs@^`9;*(Lf6O#iIx1e<Hza(zm=zr`jul_hJ{Q#qxRWdp2tKkL7vSAxbYIyrL@F4WR0PVKn14wI8<v>=oYt*;{-U>2'
    'OX)@s@Tg*gtK|QvfPzIpA6A@;cooJ9@qd({B$PxSBMk!ynd}D+G}7{Rp9^>L=?o>mwXn9qq_d+jO>6})h?t>*qXI@*xgcN)?y|Ef'
    '(YI_nm8@w}p`U?M*0XGB2JaZG?`cSGUpM$e4nI}f>p2OKgL#Fals+Em=(Qw8s6vy=-<5jrs0Gec<#^Mij=8@Vp!O@xX4hyREhX+-'
    'l&!3#GZy|9H+%C@`O;B}QMs@qTUJ_Qbx;{?W}NHUQJW5KnZ$aG^i*i*b2_*_*t%7epPxymu-h)ocqUf(`@gL}dYQs;-BLD~?_^Kx'
    'i!V3O>;W?A?_7o0#xrt>*4ru|>4~=~vE3(-o6l1s!n+LR%%S2{HMgV?&T~n0N&P1%EbL79(vt^&SgK*jF<->0THSzdXrtEIFw_gj'
    '&7ESU0vYEG#RBO5pft@LnH~#-&yl-A+$r$1w+g~LY#ZQd=T2g7RE=`-;`!a?Qn`q(*GMp-dj(cYChQ{ClF@$_{=h8uUbw7@4(Jz<'
    'Kol>Ehhb!bw$CK(kQWy1PV4=!bcYMjVo6M8BpJlx=br$X<BsHaK{LBGzhoQ&BBh7UQitZso}S_C7)kg<#t8m*^UU6^R=|KAikO|w'
    'Ku;??zeipq>Sdk7(ReU|bqYQXp@OydzFPJ8p)wXB7dUfI4x%eL5$2{!4o}c=!kHffV$%c_J`y4O8qY-Ib{2ZK-PVd?t)itM9lNaN'
    '1+fAO_T3BL&LkrIZ0{}7h8it%h)zYfR2|QBYPTxJO@OkRaZrJfECvmt<>W!|FQ0EhecWp-q`wHODl}q>dmLB$OXlTm>Il!|N95P3'
    '`QPB5r)sh=S*Q!vWNz`dP9ts))X?RImvs$MO-gfn@Fg^sL_$Bvz;cBGNFj3cN_9d(BI4qy3KP0n^Y34h#_Y)jXAWh$DwI;u6~ek`'
    'tPCI0Ak<k{*kdf;0MlBtHVAkUrL!s2fGk6>mBHB50WGXGnM0J415Y5m(!kt}k*PLd5RPk7%#zafyM&13*Y2zR$nVWM_8B!W)TBl!'
    'aP~#dD2O?WC{5ejGcdrJ;VS&E8bKV<@=K0A;S)6}NKR^vYa7jK9zBc1j4SL|_LKh;u%~rVivRG%_d8F@+mej$1Rum0YlwdHh2SzO'
    'X1D1VW-8>H5rU;b_iyq&uxS~!b}AeK^6?Vfa5EMcYz>>~-L2K#1G36xM+x~S=qp6$2mtyc+{U)Q@Ku+X_M>%vT~?9^N})JNN5IDh'
    '56&#F6GML-BiXLW7R6=<Hu@!adqmaPXk|TRysI-*?WiyvkE#TsG2*9-^{M01qR77n@hV%E?91UBq-EwEsiLYXl&#fz*zih$HzVf+'
    'kdW_DgnQsoRSK=9FfjaUdpx=q^ob4#BkENJjUXt&t5`dHa@d@**$@W(v~LF0J{j}0q;r>i=E(kECO;^{b!Gx4U=V$r+_i1Z+4Rrl'
    'dL5w;A9GB}hs3RDWm<1{?pu>%E7ffiasq8s>*exTgT!lgi;71qPfrba9(eF|-Al8+z?`L%ZnSE5LHoy-VyU1xk%k8sCB*4QR$vB&'
    'frE@dFppHVg@c}H!3R98VsQ?QWg3VbLemv0KA*YjB&&~$V^<k`bxKtm9C}C-K3;}hEl6q=H?4AiY817Gu!RD^Kybca@1g8^f6{%r'
    'g+eUeCK`ZQ*?nMPWN^tF%WcCZP2b(RVM?qyDB)u(P0UZR2ED_?beK&50C!1I#c5(@U?Nm*@V)Gu-2I<DbyN}G05S#2Qms%nH$z4%'
    '-SsStn8*|8@3TL%mPn!+2x@?BNd+xJe~FLC*XYd&jw38;b7>$Gg-Q23CZ7(_yE-qMp`M(gBQe&k4ui09S_4LXZM_VJ!h_x@2m*?-'
    '+)U24btt$J_S_H7yq;wme?nd&1hk+Bz87j=C;NmBf#hc|)TvC-+Dc1jvarwEFRpnt%I|t|Nf@9Juocd8^8i~j3-&wYfg_GHh^A%G'
    'xVtA3`sPp?vd(P*FIbJ$T`vC%FlJ;Pc{nyvbB+`Ra&YEjAk>AG8gjV&nlz;qYm3?Q2R)aN!Qfe$z%KpLV-EBa>Y)%!I^WVYTk+x9'
    'cLit&xTih(vVd;#w}XNd3xf!FOr|jVYZdP}0?y(QvS6ocv14H`W!TW~2(M@e_^w~pp)R#rA^$`!1te)keby;m6<HaZT=&9g<kXKS'
    'G%KXdu_J#yQi_E{_M0$vfel9@mqy_K;UTw24q+;t;>&E=(*!+6GAf2zH2{kye?`kyX`k^D`gwL?E63o#8T72{$x|<Kt42G^rw3tc'
    'G8DRSE%pa_9Fbuj{grO-Xv8q&SKsSgp*$12;MLVmL@Gv1b$R@urQ)oIpT(>K)F8sPl_eY?yh|-ckkMvQj)C(L^=UU^9{L$kHn{&g'
    'ksYuuOtHy|*Odwm0#jd~=q4^ah(QRWxi|4xgF$i$@7XYI{vGvIZ!gP`S$9GC1m%&hEDD=&21VL%ccB$|O4N5`A#O*r&wgMLep3_V'
    'sGaFw0;*6+iyr%&HsRZY-@-e9*ZmEo?(Zjy2D#%%F+`;qUc&DXp`4;hg_u+Aas3Z&GeySXmSwf{V}xXQ<(ZjUe4nbs_@C#UICs9r'
    'FqB;12Hifaw<-WrX0Glmwq)E1Vla?ICJ*UFZ&S0>^hBar*1j#n*3E{T`X<Kv;YUD5_{VURz5Vx(tg@EiY@ehq*yQ8$?RQ3qcG$uS'
    '9G`g2{cAl>U5$|1OfpS4M6s$j^+j)}2yt12jkjguTp3bDCq1xSGOxRl8h$8PJr|O`u+A}{7HtobB&YKYn$zG7%TN)1`nZ`#Ju*-+'
    ';Gk8x7rF|T3tEG&(H3U0FeMR?fy2mrBQUy}BUj3{c<-xp+Y*)r;@1|YOSOT+-g~8`EV({uqH-*xt4>FzQ}bfATP$NUrWQxUSrI6&'
    'L+os0#>RGnjdpD6bM9@D#`jR_PA+^4f*N;kgm@UYx1bZ8@t(~aazhl+XoyCR|4Ny}imXl+$5pTiKG~+N%pfcsK$y>ok6{-txIBsc'
    'UQ1w!K292{Q@;Uc6=@il8vWXt09h6Kqlb@tuoK=Udv^0QTE9wvp=19>(@ahZ3E-d6(COw`wTzJ=$(DcwJdcDtmRWhT>eetTK^MYZ'
    '8mWJtjYkq@Mt>dU+&ng+T)6K)M?d&}b9`$wfS<S}ry>MH;IZoK>l)?M#0U{t(s8{4^2GKCXSLKF9*D6A_m^%AU&B>uvJ}qPmR(ow'
    ';o}Xgahq>UvzYgctkM&c>-`-K;5h`0x_{W5A81LH%%H4Zxr<XvKV<+0lXcvUN{SR=If;2iDg<eLjXdUpcgL1>9@k1YtRdU51$}1)'
    'T2fJ{dsvadlx`HYMI8>QJHn6>2JgJY3Je?VOI~7aV@s0Oedy+onV`yHP5;lhjJOcqdyYcTVbongW%rI7q;@=}67C92{dzW_YdR!8'
    'TdWd_{j@2moGFGX$^I%*l$h&dj@b6xl*7+n;gGiBhw5Xt(&;I1p^|PJh2AF1JGDJ%0u?LOggS*&x|2t(%Q+Q;0>agjwt=K4ptGe3'
    '&gpRv3W{V?tw{c>2u>HRFTsP@Xy4XELlQdRlo*`QAfYQYBbJOzX~@jsC-Jt4yy_nI`JX+U0i;K3WfdpE?3|N77Zw8Y;IywV-qdqE'
    'IbQ*uoRKP-pG38SlCpxf0Kb&ropXfdA<IX>_le0c$wkEl$V^zt5S$bVr_xS`WZ+35q5OnC)xV=$bZP&#!NGnF3YCj3b0!0QM7YB!'
    'k3(3(aflTAvf~}7=aw;PH2i+iVGQW9H(n|E)Jtk&`7f@mL@i~B@cmox@O&T0v2)kGpM35qk{zVnbIAGu#|0HE6Jo3U*F944d2-?W'
    '?P?o<|Mr1u2`>pQP7Fn?7|uHbv1CUXjE)r(_@jU!95Q8zdl$ntkO6Yx^y@Oo2sg{p?dWI48LduM(&n-qay8#t4k!Isvcw;lQgk>1'
    '%SAvAsGpnQrgztxGFBe!6l6e-#!*YiZQUuAi$%~LNxyW-x;t@bOmL0gti*$av)IIBIM`YOfOYlSmYuGID065$oEaZ_@ykB=FN_zS'
    '^F`yh;VGo558Z?+AD8F8#oF@e-40SH22GU!S7kOhH}Rid!XY-oGh5_|2-`nN_R|{%S5A=R5H`4yCKvS4iMuLN)z5_^X22;P9Z@HY'
    '7V-YVm^w7bC3$a>P0vTVr%`)<$Go>Lh-_$@ybG7pn;jx8r;cJLMNKPO2WocMffF+%6K+66`$RHCEnb~h&S#c0V=`pTW;tOR(;k2X'
    'bn2FQD6}5d!!jIwOu3=CpR75Qv%{+nnd;n)BVuA}3|bO1r!W$&wVw@M?P=@(&z=#3A?N~2vJ<a%2xtkWowmBZ^!CL1_srvOEG2|l'
    '=&Q#cz>6MidDt~*k7-<1htavTLg}bTa;^i;9tr%G$$bwP_#VC+e(H*G6A+UL1`cwjhZE3=iR-1j66qSv!z@Zyd~OosuK;#pUR$pf'
    '1TtO5;L<ESmSRRs{1?OpRF(JDi|d{E-%v!BVrvNU%BAzJ4WP(wdCew8vBP4UabAi4Htx%4o(M<So)3EWzuC_aQTq-NHZ3P3bvMC+'
    '?1VjgYTm!|S?Y-YxS#0|@@6{z$^?lSP4b_R;yt5C(*Y4h()iM|mG3aE^qDtZU~V%!e*%8QHw1<~7C@B0Zw2gMXyxO1d($)KpB=9F'
    'lW37hyg<uFLgbGS|L?L+^$7%eIsvQ9-xHd<u6QwVB3a)was>0XN(zH{TBv##Y>WL-=f}6>|16C`T{*U26}xnw=AH0+BmO#KdyNM-'
    'WLrg`YH)K5j8_s`aHa_AjY1MAHSuczAI;}s!)1P#(u{Zanu6ta^3|(6fIr!`@`hI%XFwlI8wR7DF`Df9k+)`kV%nNRz63YgGQ)=b'
    '(ffQ2BSW?ZA?;U^DvSR$Ubc`>;@HIbX4-i>Bm`kDGu44+O|O{(hjFrP%Q7R?rKNQ__Y|F*pRWthf2m{&1`17EJp6KSk)!TF2@Nu<'
    '0rD?JH}vynX+nYuaEoK1TJht<>(XI-W9}HWO$Fnpdue?kkLsqQKzid$5p8>BNHCR$+4b`wXvnNUFAML@EJ(YPo4;kXGy5+1rdi3m'
    'F}+~zzsM>wALQC6CV6a0<_oq5M4>1v8!gA<n%|l_?3ESE$dBD5xh?lNsV06mkwJfp5E&#bQdJ_8BeXQL<;d}%L%-y3FllceY%ZL('
    ')JUGFTcQR6Hh6AGxe`)w9`~;mQ{Ja^w}%!Qi|Bc@g3Ue@2${yM>r7Of)+J;f7H^wyr}-N{DcsxHa&-aU<Mt<(*UYy4b>M+g&Q?N{'
    '+)D(O$jZ_4x>AQ}I0F(qLYNuDtvGz5h#MH-;Um3(W#sK<<2+!x(x&Ei!Nb`p-7mp$1Ddr!5hA58&1^zMlhPYmIEwFyaH87?C-*PQ'
    'eInU4LNVRNiuFQv%xA_qQxt5X9;X)`QRevK!H^Vh2i|J&#`J!vzycsN(;jbm1fv>k(03<z$Dv>s6Y)B$t1b->{0;%>k1l-lR2<bC'
    '5BY09Ne<Qb#cd`xbh$oxfDg8pg)l*w{|=h>{L-WmQ!{AuoN+v#x7b2inituigoYYto4Zr<p91GfBN7n^z6AT-sQ3x4fhlUMv1sCw'
    'wR@CWWecffLuvk9$#JH>6DESIWsNP5H^vfS?;!M(ue}M&lD`LJr+{O#s1d9bDpJ_^?+tAW@8Ul`h0d|xd!bl4H{&qk;~Mf-DTc!5'
    'n}On;{vT^i-_p#7rqoUc8c!+2X->|eA^wG*tT!yf@L+=lj%5rg(XEJhoz9&`V*+T+DC?F7lQx*$er<<x0^V$I{pXoGhGXDxh#0?z'
    'ZcQIFn;#T3Muun)wjaP3-qg>10>YbmaeILh3T7-w(V7K-ZcRl4B^aGT1HDv%4{5T5;13ap-*5df?+a0_NZ{vbmG0gsX=S7{FX;Ta'
    'MSJG}00^zHL{0zfU5Mm1sVtT8v!to>SxF;UQ>9I#sd`~_A5GWiaDnrHwZ%1<>H}|^RJS;-Q9{C$_Mb$Vox8*7g}@52p28iJx<lfw'
    'ca+PrCnR;ClYR&XKh)M<?#1Rp5;d6Vzf;bMeVoQG07i9N@uosTRzS!sHxBdMfEM*Xji89i@oH@+gPM_XO3S1OW7Qv`sJqF6y*Q+U'
    'th1QZKwj3#plLxx$YPnd(QZeuv8c4L{=0X+V-j&#N1sxghO2Ifk8R~be)XWrOt4rmzE~-5FvCV3<uzX)`Be=X6pr!`_QR@4IF*Ee'
    'FAod_6Jd4G!f*(@iGVDTbQr?KfoPyg%VA)LNqH7VyRpZhh6nre-BHek2Aan-)I!j8dmMG3=_mqhZ?<XFCkbu(sRc!)y}nXIIDBs#'
    'uC3sOg3K3M1+=@2DDGovzY5cYF}9`CDP8HEVNQN2ImAOu+c7tKT%@TKx@IqP1C`}NNr;!v@@_;i{g3z4z4P^);b2h$sP4hQsFi$t'
    'z2t()A@Q!GnLTC&4{J@V1nN{@jY_5HJ6sf(v$&3Q=XlCa_-x`YI?6XDq0}qAtzTMm<>MRp_0HWNzsl{iikacT4dr>uJ&k{<VRsom'
    'yAj4F52lyv_swb4$9sv5^)Y@_j5FqUL%m@^6hIX_sY#S_48Ydq+D31MD|ZQGsl$(@u+1FYvi!N|<x?f3EqS6Xqv7ceiFh_VYXiDW'
    '*MF0MV@gK|-4Oa|x;mm>Rlb|j8*$LnZ84RvK18a<wmqmRY9xe+6S`eX{n$^p9pz*?$5OVVuKZA7s8IJ#t?fBR>7q89FT2m*YQg|r'
    'NbC`8(2ETz!gSfz)cVX|%>HIhj0Y^4PO?eC^WjP?WhDH9o0cJB+Hpu%Mn==13HLUu*SnMHhn2Fak@-_xQOPo@(wqBfhDZ}~cuF*d'
    'Xancii~0*<D?OC8Wx?e(KmIxkbsN2Sv{XB29gb5OBpDF3yX7U^F}HiMGn?kRUa@$DH>+vOYDw6mL#^8+h%P{VKo0SfVd7L~Po|J#'
    ';~Pxobv1qtrtXZF+(@b-9Dpi5bG<0*t3n}MeW^HuA<;QM%bPf5Q^}JWXseg^p|}kt{s5!XW8BQ;Ee&R@`>jryR0j}^Yr6kn-PG`m'
    '!+%L*vqZB`rIc}nJ#=}r_h)WBx$Au(TDmW2Uv#~9B>JRrER3`kdh0qa#5!+YWAy@D=X^s_^lpaZHK7qor?UjZf6Mhwwm|B{@Jo-w'
    'e5nE;X?ham7LCQt9=;*Hd;H9+DeO2=Y~xcU8}muIQM1ub>x6Tq^Xt`#*$dnQU2M!2A0+rgXT>zRqrR&)_3QZ|3ojA3HT&KSQ(FIG'
    'subYY&Wkgj2Y*>_Uy3LY`?*0xAq`^I`4z1Zdg73!HYmWJP8QV`&GVKGy3oBVH&xN~-wIu~Q)8Wx!T3`mcLgTb50Y)1)XoH4SAS<&'
    'Oht?GUV$Vx;(X;TypNV<LEh}VDq9UZov6z~UMKQG@%5#0ojUT?eCvh&FuaQ?JvCGjM4)aslmCsOo*--xxs4?ShkmODqwU!`mt$7x'
    ')G?`Dd0U8V)JwtSKX!w4*PN-k3SxbH$~_Bhe^SlS?x7@w-13`p9|2o?!KibTs8bdVC5G|)+(oaA2*&6pDNL##xIN1x4=FpQ`ZE=e'
    ';lEU-AtwZa;XYMe;?~+(*t&ghbc=-uvub-vu(;k*2O#AdtU|b#l1|+Y+~h7zGG>fR=PI{*m>lybUmA{A=Zeb*ByKSnW!_x27ZWlP'
    '5L_BDFFFFh{N~B({1UdTRJ-}8BVUUVEtyqB0-1YbxWP^karkLQM`2}JGfd_$z(9B~W*fB^QWwE~qD{oXiqr37jlc-Mpqy`w)gvE8'
    'T=P)Z+Xg<|8q`mWc#5_Z2+W<(8v#Zq;KWkz<K^eu-Jx1MjkLDdFgqfI)oC}r0h#URcr99I!Dvj9{jh5jutZf@Z{FUMWCPbq{(JyJ'
    'x<3y`pqUARZHG;clw8z1)z@-GuZG+=*SvHsky~dziy*?rm<|L|r9reWS9+|&UBx@CcN^^HFh3XWBKPe>uLqkFKZm}Qo%pdw0j4|O'
    '!`E?YzuC;M=4^`#v?U9!C@z@nn%U<v3!AjmYG&<fI37SqBNvauH9kB?iOlxq2VzmV`T9<TW2wXi;kvZ%Z{0h90<T`K!u1FGPXGq9'
    'q6+N~u1*BuS%NgL0f+HZLUcg>lmjMfuAecnM2Qirl<jh_%M-^52y=y$t%_VIb<p@?gx0+d5v?6Gp5B})PDoAcf6UPzOMR#m%<^d+'
    'bi1ZG!UeHL8J?O?1n}k2wnIdH0rCLKY27SPR4V0P*TuV8wSR`__(ni63`xQgu+76>_NGb9@^BIbvrp=JyCyOoBV2Mp-A3;KHM(`{'
    '->A_%8iUJVzw3F|0E05xKtTykU2B;eJ`rsFQe>(L;&GQjD|Gr<(y;NGyidr3jK_%Ky>HWZsb(BxHhosOo^L<Xk*P?2hZ|(<g$G{1'
    'XC$kPSxJGv9pjG+OADJ;`i<%0A;<YD%*0>!Ks7N1W!=|}t5FVdSCinbEy6uE$sZFbdID5oiWy1yu;#>pp+-?yypT*2g$QMph6Cl6'
    'Ll7*vomKtN(pd@v0n%BbU)U3zL1`Y~oD0F@-3EX*nTGI(?6N&#-gT903zc5uhaR}z5y3O6P!<o^ytKVuqrbYS#z`c652hCs0^k;B'
    'aoL^l%+FznjIhE#y-8gg{VmiOHXQObmihd>U_AbG==Zg<zw{*S@K5w0zQ6p-nE&dHZ2b=xM3DEsQ?X#zp@$i<Zfm8OF61x&2LTN^'
    '+ne}2FR7Ky0$pUxV^o0-5zcw)qJ&@(hLZm9qIK;&JTC@V9<8^QL$N7-wOh%Z4=vWZF;QE>IncPdpJZ~h2*)j6X0qSO-1DxW%Y?7f'
    '9$bi*+bh>+ZS0dA6KROX3xIw!<!g2{Ltt2(=)%e#S8AHY(NqF<l<5_~4J{$>OqhUKOmrU!yPjNB)V#~^lX7HrPEKb-;SnT5)l4XN'
    '^rl4zqFdh6Vc=0TacX)fP+r*(G=aG!Ym|+>Ww>P8#p@)l+J{pI{36c<W^YcMYZP9xBuU|L34-ZtoE`i2YyMnQo=vn<C!ydoVWIKG'
    'V8b79GrzSq>M4pb%f`hFv|Ot=wKaq-qN!=lh2L}I)yP69OA;1|60_qtNSpUcEbx53UJszQR9?XNwDRjJh6qWk9oKaN&WPs+_;%2@'
    'c+oXsT5A~@ZRhcn;=4~Zkwy!@wzqdMwK;cEJ1w)R%frzG_7!Y^UGcgUk(Py}OWyweJtn4(YVum1gfF++)fw2)^^|0}jM1I!V5ySa'
    'ELHz5UAT3m6By1lDNKUeI}SmafleYsc)p!GQya_u*&p3`^=a4m>c+FD{bNJ)2?9@~L(9Am{CS9^Fpq!dQ?SgQLO{iZ?;yAl!Y`2f'
    'eY$YmAG>BMguh;Lp3<*cjVL!NmXlyGdHkYx`5b*$0zb_gKH-(Qca24DyapDpJhPNsf>r3IHY-Gr!piwomeQN>RW4`A_$mC17;eTm'
    '8aFZ??A08Q*;BTS=VoAF(LtMx?U&<mXkt{DUlsb+ACm-y8ttV&*+tEN@|95=NS8av`3+40SXg8p!$I^|oY8+Dul+PfmND{WlgHH#'
    'j1ZNl;N1H1m%9seazL2a@+0HrpR7e|IS9I>eIV}Yc)k0&qWw?>SrcdR%7`D?i%x66*%XOZ2N`!cs}MQpa>ob97FS<Q#|!OVvWnZe'
    '+yI3zVgdS(BQPHt<(|6RgdE&$jP$r2j6}kV5}G-Ko42d$54LdmvUg<2sOB0eo2|pajkK|RA=|{Nrz$RbVh(%%NvK_)tE!C`k`szZ'
    '(wQ^K8k9PYD0b#4h*<JmdbrOCsgx#3e=;9Uh1kr8EVY+t5$DU%CV?8{VHU_!G+TGLx>&7y4~m*Eq-~)yXYYO$bC8#N!%Fv)6~JMY'
    'A~d>XQL*(YWngv0fJ<3YU4!&ctax^}Bq7np8F6yFh`_v|QvQ#A>qKv6<W-ew!D9jL@y+I`mJ4Vwn0g%%FvOD2Q{O;!{%ZOIRBE9z'
    'TT~=^(47WFtuc@5XcxN7!E^(-Pz2~s5PE^3n`6rqe(zo_8PhqB>M}i&_U!U)q;afjjjh~_1Yr$O7R7@M0#ThQSjtA*My!8r21=Q0'
    '4)12dd5FoL9`dgxNYgD0nQy_B{i~dYtlD_E^DL1D%EeD;$w6uU3!iii;bm!C;RA<?Lyq)46;!G0?4L!UIKd!K%}cxaMVh$^-5^qk'
    '&KCX<71_WmW~H7o`QAVPNqaj#5(g>nvcF3XPDpgWukT=!ZW{Ffxe{3x$G+5;ywWe|GC;~Dc_^)9MC3L=OopivLuCC?XJlR#iMRAX'
    'wPXO8NI?KS)+5(#>=QPFMEa1j$ZaEbo2%eBTSuvZ0I^1d(S0_B@3}F+x;Ap`-l9Ola5XS&o^1j<kKcO9t8(Oq-U6}q<BYiV_;NLB'
    '=<Uo(U_bTSJ5ed_OmtC%W_epuWKvA_d)$b$W7iMRGmH<>@S`uMZqxVCtMk-w;o-ssykFByixuxTZvVB^A?G*BU@kk`55Xjjcho6A'
    'rkfBe&B;{%cqaHMq;k9`&7gsZvHeE_!!(A70=qm55?=Qb1-`gggmYKRgwIj+Wt;gzg$S*rWCY9|TEgOAr>oO#%&l@J-w6F;&GcAG'
    'L^$#N(zP-Y8sq=&&p4EWsS&=h<BKR8hpMxgX;wMbb^}Yi!_5-<#@#KIe9MVlp14U58!*`OxdF%XB;chxnvyBaIXL#mjo_R>Cgo6&'
    'VLLYAqKA+6CXoV{(&CjCvi+AFo1=8aFimkGami@tyI*W#sed=sA}p#a65XT<EJd(=pPSH;5xeH}`>dsC)MCrGbDFqA02c*cFT%#{'
    ';d`7?|5-mGMj_|O#g7rd;u|cAv8r<q2gRPbg67shp5Eu%Zy}m05Ov|b7#_aRk<<lCBgu2|RUb`dm?DaV<%ci-Lc$yyd#NTCW=|V+'
    '8y6CSLKA3uUS2hITxyh8gy9_rOOPiq_nciE%;Ox`Rt^0_x(z3F|7uG4dESKx;hfGLTMQ*eY6bH!rJVq<)>f}@#q2z5vmvP(kd2A6'
    'L-fO00sIchZ$f`pey4~55xLI$X8j)QzTuG`m96<K?^cw2Kh)yznSYSi7NcBU7w77jZCW9;xyaW^S(MDPG93?$!{nm7sLtS2(7q)V'
    ');fknp}zSlfJtygzRSA+t(m?!We!@a+}isMY|+=Kxrsbj6SH|T;Op-yoTy-0PUpOA<5>5aG^XyCH|);P2<Q;6I=5~)omWC_8B0$Z'
    'D}k`v6=chSm_Mu^RH=>tYU$85u+kwTVyp9W+m!!gdOsYzh;K>?Z|DLBoc)q0$zu5`M9Z1X*a>fK0z~Ky6IpM5{<}F3)F-T{pk1%a'
    'owm!4G#8{Y(<-3*XW@|J6R=Mr)M=xb3b*KYNgG`SOxx8gw5L_$qd+SgD|rwJLFI;<3Z})o;|mvTU5n;yeSyotT{|9%;CnTtWdw1~'
    'tRg}M20UZIP#O?4X+5@#lK?}HRLjB~TJmsUNq0s1-O;@dWU&9l0o?V2rD4GZMRfOYmd{A*(b5E=FAc$C(o7hHDG*o&B?T*_1?7Qs'
    'IWZIf8oFV)&vJ`SJ<fNo$ZZTT(!Wt^Ot%O#GWuG5YBLzaEtxlVPtw@t;`CmXDX#Vx*wSbC$NFcg==0^~B=S$$1j^J1j8GUFIql)P'
    '#G4|9vUYUvk}!XePUk&Mqx8Z$r(vU_$P8Dz9+dRAyle1eJ%OD9TmTv*B{RIu%L;YE-dKKv;?)DVEz$@}o}6bv<A&`@EykVv5_TUv'
    '=ymkJ?38DXzhBdg{C?K^Uv)mc@Y=@=wa09g%$IqXoyUjzjo*AU1X&}p{KldtWimCCl2Q?nC&>OZ7W$p!%&fUQV*HhIb)|?_Z?U%<'
    'l;eiHU>LhizntIcMQSmeSL36&=^8x>VkbgGbpn^-NLyWvY$zcrHD4!FZtS?U#oUVqCm*;k))?*I^2%p<+DY+@bO|5upWRp+;oMNT'
    'U|D)Ff3<LDv>J~_H9!QA$InzX=L0KI)@z43MOo|`P)9eUsr%mPm|Nv_`pfjRHX0f0bkpz;81NP8?d9<q(8D7FU&{Kzko&5h!cJ<?'
    '4JlxLKc(Gp6PyRY7uKhmOV{B)(|!l}z6Xcn+E@!^`vONUoW0-N-#N2w(Y3*SnbPH<g9tw^PUtUM=n(VM2KISRkEDNzUX#}RaCu;i'
    'PMJzb3e{w;wBN>(Qc&<q1@v2@dsI?Z@;hKjS}^tGL<)B;`<!fFz577iG<lGXugI%S=?FfFQGuK36<zP9z)`h<<g38x{N3(fc%|H<'
    '^VdoE)thmF*ll{p$Wq~<df`fAll7?LjomH%ow-~hyZv#~rYcp1!=}26>tOE+{reF2X_dZ@0T}6Y^M;*@yF;<-Fekc%x>cN3UW&GB'
    'JtPCp%?_HGu!BU*CC`G|6uZgAIns%*Quzd#bUssUV<%EEeOfd?;jyKzT+}GOG*O4odS38jx5X~_#AS(P$dk^JKC7b0*)IVYD+PG3'
    '$j%4?yy)<>-#jXgvF1ZG4QxfFXq6cvLPIA4_Sx_NK5E_g4t~~S;NWzZye}vqGA-q=ORzA21KzW_cKcnS)-y8___A~SSCKw#FK#B8'
    'gzSNRYp=HA-$=?y12N{m9$GthjvGuO4YDe-(7u6Iw-e80E+L;btZ~L){!KigPsM&Q1=aWJ;fqVD2iT$6<>70N|E1}|3U@%p*Og9o'
    'Sj0RaB8Ellh67E9Q%*;Ps8JV8MVZ0;U=zi8lo9PsYaD2eKt&+ivoA=!`BJG;F1fD!-O6o}&Idl~IJOAIUOf4aMw@A@1zq^Z?M(Mi'
    '47>enf0F01_jSJ2RUvW92warZE8}cC%&Dk0DxP4&j%j73Q{tI*yh#Fr*%<yXQ48;On2+r&URbIDuAKmkvH2=cMB_*?jq^}!?s5@`'
    '+FxmMq^LY1hFI{!Kr@GZ2@WI(+@hr16@53u>?H`g)R1t8W)-pxHBpBYbuO@Ks?5U*=o7|jplPSq57(1Y%|YPr+vu66jEGh2KqXE{'
    'rRwIjoZ4WnaygQ-^EKpzS)~LwUkH_|cFkqT&0AZ3u#@ZFL8XC$K6QeRZr%3xX;5fw1O#yGNbEMUD*P*9=;aTnJ8_?RrR}}<ujGL>'
    '=5`v~K+iiens#|;{6l*e^M`UjDmS{iusb}ZI0u$$Ki#hhKQ1AAI))4=<d6u{*1ZC-i?opAhtikS!&2=880|DZGoi_(g3qoA`pfVK'
    'zEXY_M(GvtjA!iY?&B9N=ue_kINU8E6kpE+Y$ZmG7}3<X9@1xPkbdqM70Zfob6?mXh)WFyFrbpY5nMv*v!GYTSygkSW=jtuBcj|v'
    '&5a;8|8WbXBZzjPQW7FryMu7EHiHzQixi9cDk(`%O~RrPGtj;0*?a`_TZtp&_ln@<pr6u=p9{Cbd<TR#1)vn%Wm~PRQP{EwWI{J}'
    'qw!yc;dCci7pxE34l7T?O!x+vcv!dc|GB5w(9{6@_`<O2RdlJPsE;!%1U%eQJu;M~A}_N=6-U95jCJ2IJXt7ijZTtAXwej)DRtQX'
    'lhvYE?)hZj<C0eh%7B#r;P0W{b|niMoUP@YM%Y(}%oU1z3w^u2lUk3e5xIl<=JtP;lPHPdwp0T+AHVL@9d~c$#1;2rKt}sR016x<'
    '&c+R}bzW6t04p$}mA8|MC4dnYo-xm$%)eu*R2I1~vl}BK?z1OeT)ykz!_7k-^ledQ9l423=BPLP`?3p(ZO?*J=9_opJ$U^oS7ZW>'
    'E#*e9a^$hOtH3R6yl1L=HCi<e{XRfd@%0efc22YX<Rk;cZ9}z0Dnm`I+>;>+Rq^kyhs9Zj2>I{0?tC$t%c%fee+n@K3jW9O2H5rE'
    'dxM_%&;WI<9`j(QH#jP0)iyrLeWLlhRpR2{%zA}6P&cCLnhD_9^ziP8?WPUD=CfpZ;`9Pd0PN*_tdsj#Vuxe;#qyWz!1+gpkShh8'
    'gQK~ln&cu#B_0lJ*2vOb(-Pb31E%7&Td}sfq@<g>@ZQJu7rcTR$X^#>BF9hUXKss_*h-M-9c>vGcv4-_AS};qE<1<cYfN|iGPPyb'
    'n9-~r^XsDKb503r$y3Kk%>oX1I2=EFG2`@0U6C18esuPYuZ2eQ85@-J&mNoZOPzA)*prufbsg!q$+jiL9mjZ?)YDd6HOL=OP0ATB'
    'gTdN>V=S<uJ@)H7i>`p*YiGeH8AMb>JA@JAV4j7u)x~!5gac7X)b$V7^eu~Yuqa^n5L&9b7V3Vl9^6qsi%pbgknEa1G2jO_{l9Tm'
    'xJDDc2Z85u4krfvi?g;Wuj8aNtC27n0l_P`pc@5Kp5RpHuY*~nwTK<6Ma}b_u6NnLiM_UWWYAzlbU1d7Ys00p`L+Ztf(x0RMKu|^'
    'R|IwoOi-WZdd1~9Ry8-#FBzZQUyYQrTh_PO{D%?a0-F#^d0x7d;EBCs+OKJpPQSBdW@qbVUX4y8uzeO~(%H7?PIsPhsugD%>W;x9'
    'eh2bn-<pVi1DyP=H=!GF2$m64=yB2VC$Gve$mhb$JPh+WeLh)4etr|qBe6K7MUT4djpU#1E<n2^O1fDdp~Dd7Bv>=u-u<0ya4R>c'
    '@|yjwnZf=?Zg*eB2uOwk(b5ZD$GKM7@#2sP%dm@r^Y(;bLsGJ}k%A}yS|SO|fy^<Q(oR6u?<jW}3gKJ5jl0jQKyOY^h`*|3`Tb&+'
    '{iiK+h!ieHTgFz6LpD&NdM^SSb&}z;7zb%w*E<GpA*dZ%OXxEvtI!K%3?za>IvvWpU9H4(WW*R1alQ^Xw98f7VR_aNRi_S8!387-'
    '4k}cpW@UBP*UCzQuD%d!NFOWEc*NZVjL=~r2F3tFIs2f}D$yrt+!npFVdP!4jUy}wTc8$O$X|hw{5d&qd}+{_^=+6K8+ykJ$s!U;'
    't>iqd7N`+Di!e_+oVhUSv1&ROc{^_0jH&)5voj3}N^j+yi*}V`;BD(W*CdxXs8n8JF{fceIovr=D6vsA|9i@QWghB9E!8Rz#Vq9L'
    'nqoDwZ-Nji=Py1?2nX=kK{fEy1`|8^m4caMZ|V8P^W2Ca0|$G5$7*vlOZOS`RIA@<T%(TLpMrQFUVE3#1WqgNexDdG4y%_j9Toe)'
    '3&nsQ(>tZH*h7)ld^=W`p-Ri<JIhGx@zTl;$nhB0bLldRAJ_}jAdwe!W|kn})E}<HyDbzyvVO{@kub&dbKv)$ebh$}Z@_xkio^i4'
    'DVLp}SPb>j?Ti;155%T~;cqUr5@}tcP2efGP7LpO3K+t*r#^Yf3j22Q(;H4`BqVLLxuPnD;rSsELJpSMh=4Pd48qJrzhyZ6WzQA='
    '_k|t>+FzVt!%rDtv3GbX5wEE{4mljmi3VTBeN#a_zPBPlI~+Ew8MFW3A$NhyAkV{WO={P%N6h(+EbO2mNKz`fWoyBdm^RHgfCO<z'
    '2$hHUO2ULuZy$puS)OaNxrmIRL2`I8@}VexTgvYVrQ{+sX|JrtzuXjAE=tx#YoGJRY25`B{gf~GiarzyYkGZ4AP}0B?eVXm#%FoI'
    '7`9afq`LTF;IVOZZu~Rs6+SFh??7&)&;%?4WCbqO)MbbJexaBKyz%HvLI8N1g*)j~@z3W|91PE<#oPVzE@vz{8^C2^)l*C^#enxM'
    'UYu|J%|u6EScOs>QK{wq8jYZXHG`IUm)X{O5%fW)&9MwayW~uu8W`m{DUa@SoA#yij?||LPHQ`NPUeRTi8)G*UWJ7Y*&qPYFMi$+'
    '9bj9nRD{Bl;u?JOc2!V=o_itHrMMvH_jRNSe6jrmEI3vV7p<G`KMRc5cpZpw4H7#1_r{kKUM!kd+sy?TzEgk5Kc-BFthW0O%i=?p'
    'L+fDauv~SJI49y`8p;S(m+P|%2AY$HKi>sc6+U{cxL-2X_rU|bV=s#V$wew9M6e;&$1f=Ou0nF|<37of@-(VCd10SaF?>}2W-u>J'
    '0bH@Ko&7}U{=n%CvM-`3TF`-*{Kv-{+wZv$J-~ajW@Uo|O~nqMq+bZ2?XS65K(u<Ov`Ez5M`&WBInY0z>pe~(sr;Y>+IA3IJe&K^'
    'UsI)^PtYho^Y4Md!}B%&oGsZ~vd38rO6^53tKC`|3!p)txFU-Q7Dt@G02U_x4=_r?hO+VBT9|qVVCy|;H=bL8sAh0B*B$6j1ur}~'
    '*qc|5Di^c8ICTO1wScBiQQt*Cym^%bur?r|3%3L+M{PzU-l?y}N8@@P%51f${~iYrl-)jA*bc~5QRQ6Wmm~inSbA^}{02$+<pF9R'
    '$9mN}(_0kWds%^?h_Hn*0<s&g0VYko9jb*8;^f$?wZKaQAJt)18aR&t^}mnwHs5OFS>o87XHDtgP`WIBGdOg6AOSp)I%x*dS;$)n'
    'Kr>R-B)gvNz0sa%BugHL7FzBL(2)-QmY=yDR)V}*vlVWT&|L;{`ba~H2bcCJl^$-5X1*?GO8=RW-~=a-XFsrYTN!zhY$;6D8_*$H'
    '@G1?(cj@6#O5WQaaJ$l8Q6V4f$Q((d-Iy+uqJTB@(1jz|08^P!xvxL06={;nt8kkcLJgf`O6w$sKgXRzJ+byuuz;t*2A7v9gyzf&'
    '{mSW_s3mQzyl$c=KW3%a^oxMktEY@<-*(&Y*Zh-*Y}bkL%HX);@2W?am8}ldIMv-;d~=JlwQK=meatd+!a(TZoaN{tu|p2to;>Nu'
    '2K82d_MJ#Rf9ubj26WM+$lBUQMlK0v1o<$>i9WpKx2iZj;iu5iGF#v4JaZn-A+rB>bsLqyzQZY)i^&_8EwMa15bW+#hq#<qa?Q2z'
    '+7Q^v7QMv+1MPrw@vwFmm$J(A2cz>0rLUITlfT2$G>w4F$slH;^C*AdQ~K`-{_rVH(@~JlTXU?yf$VDu(tt(5!PiZEEU<m(dDg%F'
    '@O;(CU^d1N=UGOWYZ`wFp$nbk9?Wf}dprUduM~x3mTq!b=#a)uMG}#GSC<$%`=0O!{|+R5$7wS}Ec#!KPloG+ugm08UbIm0K-Z*F'
    'qA){5LTO!(oe9$F|KQN5D1AS`?0-UE)l<VsHuusnJ>9Bmn(2#UG}ZFwZnbPc*Ba)~gd)ED0etwIoJhwv0AFEPXq4bFqTOLzDkhnY'
    'zh)b3s9QYz{9LX<<SsfL!YemfQO;M^c5n!c4P7W#G6j$LL@kC6#@|81SlCk8sM^6&UtR~X5Em#Bj=p}9>2AwekJ(9P)9is+v)5DM'
    'a<jTs2o0@_rCTJVR1uJ81ytx>c|>9ATo?$Yxm0}#!5OAq^=|{b&5t!{`fZS<4kFg2Zo^jMP-#3<Q=0=w)ho$Si8tB)WuQC{HIdx%'
    '%7)i_waB&t@zBLu<4qDx59Bm8L&639287gB3;t`Z_@!w0#us|QqIB_owYIbq?gJB9vZtB8j|N6TZU$>6XeUiQI(!)4D-mHiLKEfy'
    's7p<aqP<b*62aG#A67iB&N_m}G}4j|#dLhr1S7FM5#`R5zUu4b)NdOQ2J?i{I0fr_Y7i`ep8GP?pc&k{mQx~CDAvwbZ$Z^WM9D;u'
    'jvrH7qu=P@w`C}CPxN(~t+Y@&{69VIe5}4}7{I{J!4K2^4NIndUU*w6IhGSURXWu~cs5VsIY3V$D{dmyF*K0KgbFbSR@YU&ahuS|'
    'A^qLCPxLPZ-0l3>H=#Y)<nX3BH^Jt2{(}{2l!a|Y%(H5)1XhC>Ba#tc^1CeAs8`{!b|nim>Gpf;5ewR0L6~n=DqWNy8e^Ov>}z#>'
    'Bc@r@;x+~}GkhJl{IK@JV5tR-Nng8&tp~C`aX>dffr&UmcOnX1PH{$qW?nE-OyLq18EpE}Jkz<8u=;whdr(>5H}eRTQsIDD!jxc4'
    'TP+>uK`b73&)fAMnvb&*xD#GOfpPZg%HZ0TRSIw!@j0vh<{7TCJ>}PT&N?2zu|4jmD+-H#r;M{@fv#xEQ;59#qR;Se7kD%uW=5a_'
    'TwI~f&>LxyA}4)16b26}b@sAf#Wk32jqkiAP6uzVHgP#VxktM-oZ~nQbs-m8i6kpks8y&JSl|!tZ+Kfc2mZ4$vME9AhWLm`8LD0r'
    'w>!v?yC0@IE|7POVt)o<@&!l=VV42P_SYZs$~N)53l7nd8V0V{v~ew+z$!#wSi=&*RM2)ngSs4LJDu<bQtk@y7f$XN4nA)CPWP_~'
    'e2&K#D5!eq;G$fgS2UiLfnVQxTrCd}>?BS(hj1|C<N;%qqfOa|{<z6<3=p{IUaaC}Fc#X379MD1);JE9t9W7ccurTGY8|LBP$&S4'
    ';d8#FJXTy4Q*D4^ee}1Rm7AG?kVPa;<wIrKA(5pLUedmkzUrBXb3(u17gq7;fO1HdX3INisKvqDD)+C@7eXc>VgJ2Tcts78h$LA|'
    'MZw<I1HQ35`X7YvmWj>0)PjV7;~3rCae*+{dQkAxLrh_mTGAQH2z<LEF9(5Acmtq(IF4}OXDPGDmCZgzU4o?TD>~j}LJ)et!~Qhv'
    '+Io95tDI1zULJ0yrEcogO`!;9ycxE*PCA`qdzcH$FY(g268a}1FCMX`Pc|#?@E(o6;QeX};iQ#%Bf(9>U=|3GSt&)|H~7_Ejeajz'
    '%zq^qpZ^|rb^yEn^#>1_Yz>cA)Ug<`>4CorUm_(o_p3`Fwj!>mVz-C)UJL<LMfMF1M+RU^3oLfzA4(Xln^QVtkx5_X<bH#(Pt-3;'
    'RyC0s%dWk`R7+y?iCo_nR1*g85@!_LuOhKC!hFP(`v*(oNvp!B+Fa3;u%;x93!=b@#1c+5Q}<UV?C+nm2UOE%0|b38&XP`XeRO%Q'
    '-PG&3t8k>LLwGM}L584~S=<8B0i$w(3;Cr9fk^2oj5rss@M|XU(^_p*iSmr6*g>Js7XvL;SJ%rq7+_}niPb<2cu|?W`0ud3$PB?N'
    '8xw(b>0M#41)!ETv+eE^EbpGkRDCRz@n$dgGv5OVh0kc&CtOAyM!>qO<7y&iu)S2|?K`R#3IJw{Nn5vUxoMMGI<kTwIT%0A%?GHt'
    '!&?Qnhx<KO?s?m`a39zE{l1KcmI<llGcwLuIt|ZI%n@ybPSpp(yXC+Zn0F-?WCqj7JWvNEEGt5ma^AW%57iH*Wf|f%A!w!NKk%&i'
    '+iz;2g?V@-5@=Xd)$k`($>EGXkBv3!T8|mz!KaYLI?5EFM!N(^{a)?!Fi3USbx^vVr3alBAJK;NJzoiR*-(2FURk8A5F!oPu**%}'
    'gfQ(WYY(~BL(mQVGu^GI<_;P#cDW?wxa!#<?rsWQFvYCUJ+dSc+B|njT;LIh`kq}CEdc{Xu0Djk%O=FL*;8pgpCyqCE^qkfnUX&c'
    'U=qNf@I~qsDC!=R)M(idn&3WvNYorc9}F_-3#kw|pn8gn7IZ!MU<?G%w~F-XhEe>MqKUzn^wgVh{k-sQShC!nKRxY&!zL6iQ0ZJ3'
    'hK&!SDg`!Dua*R6AyD#S=kKY`p|YkGvx2)aQ2O7TEW)9(`NxBIOqHn;9J;9UX9FkYQdk3vi`}+B|7Kv=2<2=g#UXuFc^rb%=ldb='
    '&gr64Fbh@Dbw(fKn0!q85@XH}$(dUiKM!OkI1+@!u-BoW3d`tT3@N`ea(@$ZiHlDNxt#`A)cjIURcRKZcganys{m#8Z~^kP51nwh'
    'V1*1bB4O*@zm4$7E55Nx8ide-S3qOSDQK4sDEIoS_?g^Gl+**X)K6*_+U!@5RZgiMQHeaH{OC?>7fSx4$1LqF`|WIa%=F|LyQd}+'
    'HlW{mi({~v>B7vK>Zeid@|yn=XO+((BI$XS<#7i7@TsHtH{N2WMJER)R~+IPo5&s9DYItqos`GR$Vg;GdL(07=9OH7_S2DIgVPqn'
    'hML47CimTGPPFRi6;75V<xf0O;t%nt*?hSKs3u}dA6Qd$O_ox$?rJpTm}5&zE*3~pCR5y&wBmewpSoZs#C?Jq1QBa#L;Hdr;B4~q'
    'd(*S-R!z|47H2?Z3E~wyR^7_VO0=Ha7dAm|fVpybm95aI>yUU$Oa~wsK+K{y&}%i}-7G|p7f01RzhJreBb?C5snWqLGoR#$<hdV*'
    'B~4exc`%x7pTqf8*5SRl#2e5P>IHl`eZl{hQ|xVNnf;1_;J#mIAn}b|C*hP4{M;ZE40~etCO*$5FY=|erBuHeH3{(A<{4s(#PcdO'
    'W<T{SP9Um4uH@|iauCea^+4u}HQ<UeZ$|dW1P)7jGLvZ^VBvlZ#v!u*khsQDp<RWOn%1pmT$mwL6>WUsB=$TggrrmTBcyXs324T6'
    '|BK&C({Udf5Jle%&{GxMk2O{9r|02??<~V8>F}bb`MC7UcXIn#MKTUCdv>A!Gjn&({mk!vD)OeT2o_0mROff=6VFa(LvD#?h9A4L'
    'goPcRc}&-=-%m_;ZcllJc2Bly+z{RjF-(zVYSbbhuF*9W-uaY`XL(_9aQY>L6@Lb}MdF2a%KAQ_gPl}!&@=>@b*UZ%z@XzqAKH(q'
    'KUsMENjm^$zRCZSZ>}ahYr>!qb<YmomaW3DIW)xW;N`XBUWdh)Pzi>_eOGn=o-3GbENva9Fz&x`TOBXhu@F^gCHF%`6M*CVG#+tj'
    'bph^_M=&#;0Xg$3Wgd^=F&CKj#8noWAm3{Q4$J4jVZY14b41|HrLw>_#f#*Yj#vH%35DGO7<Ye+!`~GCdTW}`R59gJTztSx#Y3d$'
    '2b=&3r;MraSEhD(;<2*^B`eVjvigH|?(hH}0x?jzB1cJ>6d{fXtxk6g!iY(GL{11*X7-uCWQ9xjINM2nXm-eEUn-d4EBBwA5vd8?'
    'osT8#{IQP5gFovpPya{x9A$Z3@u<V|GC?4Wo;G%|iW%qa0!UcI)1bSe#f$HwAZ=WAQR5FDVqr+}iBGHTc`4!$7%*g8G41Ognc4LG'
    'vN;YO^2xnwFa&ZH(?1=rZ)FB=YVuxLX7atK%0xp;Uw;m-048jomAJXL@f(2@;y2=#@6RaWzf%eKCn{dd)a~Cy0X3`Inu9DY`pyNO'
    '{IYfE6oHeSX8}cg^!h;Mfw)kTj|MCj<Mmp^#il-1P2o2aWBoh^`@wusx#pY}5xQAac*U6Gq+LEZePYsvdb&CRScN1Xk6S(nRyvK!'
    '4-s`?6HFI!_%+m5fvVJzaE!*K&HoFV6~GjvX8j2z<Qd}%*^GQvH-5LsiSB2flO0jq`?ol*3rWFyWE1Dz;SC_{QR0m-!66mky24n@'
    'pq@Rg_P05wEA*K><C9|Hi(=#^%)ZOwz~X0|yxw1Z5nZW<!#c%I37o08cXEOH&sF><eSN2b>7ox~WmeedIvUJ0mF%%lEp;wYlu%pM'
    '&B{?<3BMg9a)H4V7{y<-xRAn8ei{$Hp6Uy-QiNQuC2Mxu^-*TGG=}{#VEv;WUD#GRKLDJ1bMyAs{f65-M;PsqPbSS}?<$)ypbH4r'
    '4Fd%GY>~<$gR+x&v5;X_YHLCFq98nMvA-o5q?358SkU?><%ybi3+=ZoVX~1ViDGx%GRpSnwRIyeh!VdCZu0GFh~}cZP_$0zPO6C^'
    '$jvq1$tcFTBHL7L27Ou+T3<bSKgG{<veJd{vs&|w?vVRVe0LMIAhBou)z(TJd7l25B|kMZyag<BlSmhk!Kc0Z%4o2yi1}@u_sD6F'
    '!P_k|Pe*dqm-EOv=BD&GrH*vXsv<>xuTPf-86*{(jOnmX<?lpT69lL%IwcNRvpIs0BLvTDuBT+9$XX=?8zMxrYLPOl>uL$;Vfwwh'
    'bb}hq7PVF?$!OOE0r_1NY@3}=(E4X4q`#x~Q2LSfo#M;Rc!tp?4Mif9|1I>Fr<Agvdu?>)vpf)QpHY<eRCdNibEwv^>Yfy`lhtls'
    'y&YuO<9Z>0o`}7#c(zyrn(%X5{}pt>6F4^g-_dID_I$<~-ruU*7>?nfHOP9#*7V#k=qScL->k@_unow~z@0<)kE(?O@U3;<3^DBR'
    'f9dMqC+yZ5jj)>9spc*L?8B3yHfz!C&vl}7PZbfeIj+Fa+`37SZj#S3IHNuz|Jw|M-rILK2_x~QDrBuEg^h-`J>~f1OEaXGQH0SI'
    'FkF3^kMajRh>fMxThrtQy<Yrgur{^w?<1xe2bnKH_f!?2Dy7bqI$_sf=bGZH#}BEltc+^=aex-&%M8|d*Q~Cr(KpDoS*d;JR@VP='
    '=-@L1@@lJTyGq3-NC|%h6cixhY*7H31Mciqie7{*d95#_7LIoV6V!r;O`o@W=M-Oi|F{Cu?83Q4#tu@SF)TDcVN_`UP$Lo^X`HF;'
    'hL6flxjU3&Xvr4AIzk0sq}1Zis#=u1ER7-gO!h~j2TVtCH|X*pT05qbCyhY9!GiYaAdZRs^$9kYr^!9F(;reV?=DH~$%9B;ukJi*'
    'IdciICB~vAMc5$@4B~dj{!Z@AJG3lrmJ%kcY#%U!5OwTOJWsyg!?`QkI^bB?o0M_d=n_s&b}R9GJQ)%)PaU0#{(bJ~I3gW%#!m|9'
    '8svp=d40cPt<Emze&l7}0DpdWg$9+uxG;vr#yvXFl^iy3N1GgXt+9I<q?Y~59#3dgt|%(9^F+^!*+dl&CJ~Mg{c=}b$t$!IRg%V('
    '5M7_szt#GPNhoN<k@oo(#wK+XnLfRr56g5gcOv9D$TlagH@?IWnBg+B9MMe(a_l*#xSdz^p`A_A^W^PKo;RK;HJ|Z|4oNeu=U=6C'
    '8XCi&pgW2fOU?(_JqDyhJ9?cE48L2pPyQ=z%QEtrT55Auf4U3nl|10uYE^z1L)$LZEAY**v)@dI%cG8Sn^)rP4ZFsxw<LcaF%J=N'
    'z(G|Kni)kC>ifN%R|gD8xYL+z0%C?3aAoP6!|4lm#5)NyV{EI<*Ph^ltm@wq<=*Dv55A$#oOIW66K>}{e%r#XF~;E^+IPfa&={{?'
    'rv)bnDO$x89@4eTQydZ|<t>qF%yG(rBL!Pwp{T#m;>F2;_76srY9q&doNH7Tl}_3za!ad>%baG}i=YO683V^^-`I37s;B>}!f;IG'
    'WlFaf@?FQV-v54Km7DlM%n1`W`i>--qVGcE3Ta4q?y2qKaBbV(JDI%TsuCSNi{Qf@56tY44;mBez}$LLa{)+OBR<wp$>7Q5LsxOD'
    '7Mp-7cG}=C#MIwe?BiyRx=33UJ~Ex}ktG)_FAxWbntwr(gXI6tQjn06O(sfiOD*!3;E{=yo>}a01`BjrLJ?vit!Gj_?rsmNMFq?o'
    'DX`26RcBWQ^yd*;=rLwE!2WWgh=#_zovy0!=X1h)ucbidFg`1B9S4JbHa-7f?><T1uAprW`iIys4925ip6oJ7vk=3f&QsX1EP)9x'
    '>;I#Hj8rAO5fGub<BjgUlhPX=S01>O?()#OqaT}=eWP%<RgTWZt6`ECBlE|a`jRXFT@4Aw<nCAs7(-&&8>oWH)~*H2j@J%t2d#2M'
    'm+l-a#X2lQhwofZ*;0X^5Y&NiNX%#}t2doB0`$Re|IpGoSg<XV`f~R^?^aX%=fEeZVuM%ePl$(MPK=tlB?f8qcwbN(mfw3mfyaJt'
    'TPhfBevtn#wA!J=y{>Wio@A&hWI+*!jM;Q`14!8j{-jE_$ka?FNKxN3f5Eu%z4u?r*j1-HPqZCgT_Y_|y8LFU0y;DwvLdw0T7^oQ'
    'f)7&nQRj}#XWz5J9Yf;c47Y3d?W4oGgB10pGxo-kpW>C*TKiQ<IU3@EH@ZY!t97z|L)wPcHSnE9;1eac88X!^V=dOf4CaQ%>Uf_-'
    '@kYNqt4>=hZ<#6nBCH7EDY>+-6D5msB+KR*s`_uQCkSqJ<67W3V0MHRmUWhDUqt8Wexm*x%M+$GDrZU$7jMiqg`I3!=IvzI8^@hm'
    'A&BKZY~u=HKsV@ZP=N257Zi_Hn#<PtO2lAaS@Ix8*U6Nsx4u=hR>F#Da+v?Nscl*V#9R_7V|50W6HhUMgDEM|lnORK|J13=k4Sb+'
    '*VvTw!Fp=e_`~Svh-7eMfx8LMKh>X>s8qEsA#Zn_PzFAPOb-&Zth&F?P!ZeR>adc4goR1`%`@%0@L<F{QuS=2OiMdZl+c{2ry9-~'
    'E`)KmRAHyF`+!5uM1iL19z_UZ=b07>k4ZED1b&(_+FUxbxA)u;*~0_^5eb2es_D!HY#`<sGVJaESeLA!e!$T1%n6Zvq4<j5PES0V'
    'dvFj(YaEgX6xsG~d^ER4)$2yQm?akMSM1uW=+h<+6afO4H*4iJjM=<+>#M7;f8;K;VSB<NsUcn1qZs!yDnyz-Nv_KGhZ4dtK0X@?'
    'lmI8nC1kds{!Owu)=yjf7yo#yi;cCObXh1j*jJM0kYfP>ZAg{((<VjjX%CD8!>KETUzG&k?CPG+A8lLQBO3A(_Y;toU_qx#QM#vv'
    ';*2fa^}HZz%<&`#<_MQa$F+l2v*io>qF^ZK`H?<NYPRE1l4MTSM?2|HbSijlo_L)wU}ki(46S8$bbW{bLY5q?JaZ5pVSW2z_DWoB'
    'UknS9sMc8WwDrx+xVd%GSwTico<TngD=sTSpNja6i#=Q7O{<UocXgm;7u1u}k*_W0OI}_%AxDj~j-Yc$5IVeZf;fsb5|})H**414'
    'D$V%EUt&L3+2uUIZrQXR53b+0sOMSI-ZVYD$26JhpKSMOBHq;yJw4wQP*EqBpGcJAzZgQ}&5104-Ux25`)pX;;3vgGz%C;NgOU0v'
    'aI~#3%?|uy4uWE20D>^<O0u?cCbalF@71<8a-IsdOsCxApISdF=}3z|&MD6Jyl|lsXq3QpA$HQ(ONJ+I_py5{gG7Z?N<yIK>EVzQ'
    'eQFv|<V`gB8r*@PrER(Q$~5A*M2IMQT@SDF1mLAR*4*)2c@`W1fhab9XmmQei)$jM0seZ6;%r}6`rc?z2Ebq9Co`jG*REd9+Md5@'
    'QX+e;^HXsh&ZCcEn}=8IIX=_DZ`vtmV1tc4B9{2GpZ;B^+RbHV_Dg(R#zC}E=RU=#6bV;<)xT5=9{BhFYVrB=GHOZIB^LrpFX!>n'
    '8Ho_vVQ-Bpl=|$%c-G{Mp4{T)!6ZBXyD`jk8rO`_D4RO5P6g{UDvDJ?(#bp^-Ty%KyY8C{u&r-ikgKZ420!dniCGqhWR_Rhu~w?N'
    'RzOTay1WJHT4X_0Wm0S8%99rimTj9Wz&|?jH_n5^1XHmfC6DUQ=$hQ!jjNa;?LYgjh~=S}vT%Rtn4@Sh%q(cVG^;^(*ocMsjkGCS'
    '*aOc$bv~5knHqY$${hK|KLt9SD^o<gPrl6gSw=%#`MN|_pnSIbN{dQ*+P5AAm`)d$1-|&P^fj(Z0+PXo8h+sj;p9rTn-;ez(s^!X'
    '8Tf3}!9z|Yo=T{2iwow7>jE7f$iQNT4p*EgVuTB}*KJyN6vASmH06A&P(Sma@<){z+xHgdl&`ry4Dz|SK4MQ08lyeDlr7^NlmAxn'
    'c7@^?WBtU!?0xMVVMB&0)|izkp2z4Fd9WfhHJ_AbbHK+B6wWvf6ZE{|hbflPPjS@V*t!gC`+Qi)AnqH5jRG!Yl=*v9Je?++XbvS!'
    '$Ig|buXT~qjJU%|B34pK{wydNhrzccN;3L7k#y@Cu0?2};Grt!J^Acr+dFVnB)O)tyChvb>@f{ER3YeUV(tQXK$yY;QVndjEds8L'
    'g>Ipn?&j8NR(s=rRP|C{xIAB$*uqJ-?xjbPw`)Vh6qr;Dohe{FV<j#3UNJZ=^X=iut7dEbZL3L~x|rfYT`1MrH9Tp3Ws!q17>?1x'
    '+8BGmB$0NiW(6j5T|T&3^KEPo+kLDXIhQCYr@m1y(`(PHu7TQ_#mcZ*u3gaQzXC^tD?((!gTXK2{d4^3x_sM6`<t4%pi|Q5NhLki'
    'B&NI|Gm=@%0~!&sU|nI3xr?;9rr7T>3bDaCI%yAF)5Ny7KxgNel~g3A0=anZ+C^SL&DC;RdvW&ReN|RT3(ZN71>6M<?ueyeX|k*3'
    'sXf)%REt{w_t}a<&+`vZL`~oX?KK@u)0cYr1VRK#>igRY%IaX&+z_6>u1Qd*VmkTbTI1;*EcC^p)pnk_m@lwYy|JD4bdMbXv%pMd'
    'JkI7nn6!Vnv7*Bt0;=;hi3uFpk`d}$md~%grbARQzPlkY&^0{CQ0;Mc2S(hAnjTNdW2le*J+Jp>#&eN2RQksj4!dob+jAsY7EMkL'
    '%Ca~Vm}hTVL5+(UZL6k>ZbpRkEY}zZV<y6Yl2~d9Le!+1hTLV_j9^k4o9@kUha)Kl>5V9js@v2wEniUZ;SfOt((aXow<8tTp%p8e'
    '?!1ec*<V*Br!B$#e|FZpms$@C|Nj$>ByW3`U-H3;7Hr<6+HFKE9v*0P5Bq38y{oz{ARn>kj!U$^b8H?kN}=EsY%}Z_B%t4fj$fhx'
    '6hn4`>{@Hv%v>38wOCE@3OdxHtIm%L<qZY>V8@u0dnSjve3q;(k!x0Fkgnh&yYQjKIw^df{A7Uc>amq*ysF4C@Tf%J)(|mK+ZPG<'
    '+@3Yl*`*r%Xxn+fe0QJNMm_4qr?ESSL2Fby(@aRGWnX0+=Zon-J`CH*5;*JCM?tE?SXmX{Q#0A^L$4+TDg1z`SF_T(9exU{RQ-fA'
    '5_*5#+wi5;$C@AjPmYj0IlOkifa1ISdE@DZERFeFtHFMV^V*H4mkz<z<F)eo3)Qt|?i$$WoEkN)xq(eMb+;gth3r7W+QU#8ed(`g'
    '_+q~P)f~CXG3TXpdtq5_ptX)QpYpFU0v90q-T)DlGtRTUbJhgYokI#~wS&`mAt>;;Gu>(E!y&HQxWw%X7`xJ%Ze>pLcf$;Ho&d>p'
    'N1b*9bAFT%+gIDL)Kjg)BA0q|6$vDy8*F@~I--Lrac{F=B0m5}$XP}}G7}>FR3PW^8I-J+6$$@)Vd1b@wO+#O&^K0U*25$m#V(*r'
    'Bta5ah#^m|2Jt1{p1sfk<iw`XX|EKMoy<f^#}cz?!GlhP`k1%*`6JjZ2TsL`+3*=yi!D2(0QYg)8;Te0mosE;N(q(S<l!^HgL$%S'
    'Xfqs$Q|jJ*@;w5YqlKRz9W^YXMT74pgLg*Oc4BpRaco(ZTdT;9L7#>6ENqbnZI@?J6;ikn*apWKtMA&n6(9a5@uOLHGCQPr0GP6o'
    '6u{a8=~0jaz6Yy^Saw?9TAyw-IMXxoqai;rWVscUj}gPgcX`1aHczxm7r1_u{<|W3tGSNpA9CqBXU%72TZANHXAA*N*fxGPix$zO'
    '@dyHrIvyQJ8rkecBrJyg=YDGw-MS0k*rP}Ljg$oF$q(OnWnnzd_U0mrZE4?CzHIMr9)2e1RwEM^T3lh&Q4|8coqM(Kd&i-s;(6>U'
    '85I-JJHdm6csjQjHDcHvw{6h`n2S`bA1Ja_mjQ*sr@HEp7L)m$BXHLRKLn<M8KUx!s_Dy_l=6v20?<V|o)UVvv74p!muF+gZn*dF'
    'QI!>tun^M-NR=m3Rebj%=v9RhTv%N6Ak|4@jOLP_RpGeThABg*uw-u(gBxpaE4TPc2=jO!A#;#-row4Zy~dEd1MieS%OF&|Be_Rm'
    '$gTge!GT2R&*U@qJn;4R{~*1sWqo1`(;-m&Q;ceBt19T7whp1J#QPr`bHLVp#1)wDS`dsKDZg2E<CCZ*WqN@9N>gQfvC0tiOo>*{'
    '&;Ui1(cr~<mm;(`ai}33>m-rXBhMJ#MrU(fnf>Kwt0BLhd)r@A!nR>Khm<$tkY6$fL5BxPPg|Eu@k_m>{E^gUuk%!Z)(yw6srSps'
    'a#%2`hp|$La|-$1hkeYjjqEbNeU2gRZ_`Zw&mdNkpj11eBKRgkBo8%sI*sJ=0}mj8{gFs2x(E&*FQ~1V-|3@Vp5Q@Qk)h%`du#@r'
    '37a$m{ZT#~QqH?|!4lZ`yh;k{<SuyHS0t(vw4ET+k{+=XmgpZCE#+H3UumJnz`M{mAgqNgts$wD`gCEG73}q9wKi_AVi;bkO4)8X'
    'AZ{}aY?CrXmCk(IXTNskO}`n@59@sfA{j?4HhS<|A6fYqBX-^!5+JB%YHvs%5o08p@-sYp`ZIvoraXt)Hogr$G{N$urwnEb51Y%Q'
    'Y_Ib_JpQQAZZ^ncS}sRAN(_7>ExYe{U(B>ltA=MIwo3c@u&;VHr^oc|mV-({E^zTO_cH@j%}Lkkv*_81_)d`uMC421iTP=G*=YQ<'
    '*^?AVvuhrZBk-R||3NzvQQIMs6`iF?pd+q1x>NbTEv<IAqhfcAWh`(?&H<v7Od*@K1VVbnqbGs_Y2yt-ms8|0b7n-W@fVw7jH(#`'
    'x6WYZn!ZG*)cSo(z<37*3HmFFa_8Ofn9Mn_ksW|TZyF2`BvQy3qL`EnXp6g1ofv#!y<8cGmFUG}My^Sp`sy6n3kYBsgZP)%ellF*'
    'lUT@IyoNXZ{X7RoQO1pIhj5|yty-#6Y^jYt5_NHQn(AX-?lWjaXXQo64ZJi$9#>4-wiX@&8c)+S<Gqcz#pi2R-(I1YIUs&HP32hS'
    '*+8&9O5IIL5Z277VTw}<l}_xwTGf`o2?|x~3y1Tz0?gzE>6ex}(r2F}(Aph-v^eQ$>pIVPBy#=6aK##gU*LhEf=B&)>e=yR8_nQs'
    'NYBdOs)?K_M2s3vSCu0fS3wG9yh<`WTSNev<)wpwMR0H<C$8>?H?QpmA-7+hmjP%&?BZa`)e#@ZvXEyHIzDcSP$$7vjwMa&ctAR4'
    'G&fwm!*cyZM?wRtV7AUky^r(A)+rz!)6E)FVuX1!!#STo2r!uR-TTmBSU%B!$7Z34Z}4I8;M?`%iAfIT&5^=HH1P3tIUAduNq9IB'
    '*)3()5lGZvl<x*edKjZ^Wo#doPu}1c40$hw3dbM0w(H*Wo6=$QuJbja8%|M%u3{LkJ%kr6d^siwB8N{sds%wcD`2en@14VvlWtHY'
    '{#*X>v#O)Y1+Ok2c%INl18yJ1Lt>?`z&Mio#;AExPtM!cPWF2=y>TnQ*SNf<#sT~!dH}QAgS?-1EUDlE1)m*n24YnHANaN^H1`j7'
    'ZH0L)xE}tl7h(^LV@sa-M!4$XAj;dAA>O+~J3lX!urXxw{WY&J*7D6mYlb1$MXw=1(Io;SQV)m9w>J)AFmo~IlYc*r^cGd@P%~0w'
    'y`>hs*#`A~X!eOae{xktn60SHJCS#y9bu)D!NU)x&(m%Q{%(r`<?COP&U|MbLcjS#??2(FQ^LEQ-H&4GgXBq*skh|@FQB?zx|>UQ'
    '<%KzPY`^hTqMOCu;Kkb{82@q3(j~plpG~d;Cf%{GaHk<1vzNXc_M)<E837$FXrG8uH<jc?nm(ULN0-D9@Pt-{e`Zx3iF}+@XM6MO'
    'fKQ`&U59zz&jOsyOB~SRD%e;1-3$HU7Ex6qHER(^zUwy0FE6r52}>FWl^$_$1%?YNCoqIZ>^6bNgblJeKDzi$Me+C1>;ha>gviai'
    'mh_WH5IAf$_!-kbB}GwU^uLnZhid?lh4V`zUf~X@iG<Lh1aY#&$J<_axlGrl&P5o$oVc8tqv0Hwe~2Lue#+UKg7J&+#;9lX5EF|o'
    '(iIt&hoYZhEWxDif1D&f{r#wpRT=fgFM|+PgTZh3LA(8c51>@4`6Uh)0lzg0Hcp((fb02By~gk{OQ}qxeJ*Gvx1em>Z@Yw@Ks?zt'
    't+sKH9(ZAbyC@e12je4pl*^8jK8yjT1Sn3uu)M+JqFA3`cB8~18BF=3l{jO^Fu$;olPq(YkW`nmdG-yO2*5472(0p*p9df;ZWxS;'
    '*}7T}fc>msEsiHe9lex9jW9nWJi#AR?x)8f2QB(>U~_+>j=({<-?7ZhI%*<12H;QDyh<J4psxkd(JGu@i|<VBoa!sk`J-!~iNl`u'
    'pEukHbA`wD<XqeSgx@YQ0<=D`o=<HX1Xwl->ozb6#~t~3*N%Zxqb);kLew23-XEeEsvoA!4<O1BRijEF8!d_gftVI)lYZ;I2WCmA'
    'lAoAlCFS={e6aRBFg791!F?K=J=p;Id5un6!~R}IW?BigZ^bIbKQNQS+SLT+Yc>kQp2G`dBd*%MoDNFtm7HS*c|#zH`p7aL7h<>+'
    '(}g5LYp}QG*#CwOa^@_k2`Ti@HET;#72jMmG-G;=xfPq#7K~NH)4s+7h{{DOKxV>sLsdj{O8FGV?E?<lvTPxg{h*P?mkPvYFK~F{'
    'FIaF*AfTF7mWH+nAP1r9b5-3mQAf(wdtSRtPcF4We~0{55F|*=B%C`2zh&#tNsQ+m*Zb$Q`Wk=QNi80RfU^n*hy;1ZgwwR+uO#iz'
    '(yDZKlX?lzWY;TC&p|rf>VIgZdpt9??E9PZvYh4~R*w{d8rVK}N>|!n@eLfuL;;3{lp{QpxF5ZyGh{x4WZ0BQxAO<7rv<vWQqZG4'
    'n|~?{Sg<#2AhWFYp7+w6T4luA`DHh7L7Y7fzO(8dD}BbQxgHN(XBi_j!66(vSb>;)3oU{147D=Vj*x}OL6mSCTWa)S#CVk8964Y-'
    'Hywd=0s=0eSBv>}2HCl0yzJln+v0$Pj8F(g!AF)62&d0lCWhP>Rj!^iFgXT*mma0l%X%9Nj@`I--6MFk?sFTP^PKm34MC2l>g4z9'
    'S@M_s!SWHp__QPw?dKHnxk9fZMOia!(`xtygX<+&l5Nin3_e-YFj%dIb}%)koU!{>_*+2$1Y!NXJaS|DXRgdAA%GHTY=A0Cq(M24'
    'ZBp0sv$ep8QEiybvDWIB1umWw@TC%?<zGB?>Z7*0tPOg(3{oy!$iKyavy_S_bB$VzFz37VygcIwPq2I5LyZVDus2;!+i4EdJ=l-M'
    '{3Y`U_(w~DWZCxl(6GAt-3rw{hTsD;7f!dba<ignlMBmqY#}d<H6~|%|A&gPLi2%Vpy1)Us!aygbpUm<f4E*1BY5A1Fo+K}069S$'
    '0BYA}VlRNqtEYu<B#j<GC9=r}xZjVsj9>%Bpr;9`t%CzE!CN>MN@mY(2tV%QZnfy13_1|Za<pGA63Yj6JlgVv5SX*}NDv$9mveCj'
    'A~NGp_4k%X;#G~qtP9RBHZ7~Lq=;o9bsICPj}hMhWZ|)u>))X5^&olo!px8titgPl^UB64G9v>9`PBSH{1&zaNiibYvr|234V#dW'
    '(M+;n^}x_dhID#_+#{N8EAWM)EzhYN9>EtTjTN-GCB`{jDJE8Lo`2Rb8P)60N(@1t{5hOXEGcrcpyq3BcXco3Rm9g3>K}U-2wmNl'
    'E9ZfAu-)fDJBq-&czZ%j<!UGBQJ67i3u-LLs9`994WhPy`yA&<S9Yt?nJ$qGG}JbqVd$<peB<Oy$gV%Jw_sap(R)ShW24)wMns;B'
    'D!J|TADf1Q)jzulB%&U8hxHm~M4L`AMY)bke7RUhBN?k?NPbC&MMtLR0pZOb{Q3P^#NMbbKUw(ihT9H19NZ<F)+U3H(+{A4k-g{d'
    'vOchM70xjC1R-IU3A+-f)OZh}@ltP(&X$Y^CrK6%XK7t?nn8u9L{U|NdCG@k=(0M`Jc#5>OED5mH7!i;!@1G$CVG6nMWBLVGHHQ*'
    '07)bMojuQx0A(pTad6|$k@yM;EicJ|s0)dZfY5D^Fp~_aDYdeo)un#mVoPGryqP%>_&m<Ye#{w7l$C4m55FCC25Xy)Z>w92+=*kD'
    'D|EJC-eq5OpPvdDT^dnkh<Hvb(avOowSg{)SvHAzBUm?RY{|Fcw9I@^5;c_z(BsavtMe{XI|%chu75IJ7g!TgvnS}Z6`EDWcTlJj'
    'GIT!^`|U!2lziX)eBg1SpXcjNvlw9q2=CL?bBwIa1^MN{)I7UhtQy_bO0N|M`kwyIBNcevx=tV|*;wL-+iKxbe>ImiQ6zl`FP&Ei'
    'b{5`GfDp^~v=1#b?qEDM8S&I(G)Faco!>I}GfIU`LTVWxHY7L+lPE~0@|<PICG)?TcziU{sjSLX(zgF62<L6vSB?tk%(PPyAtwGd'
    'h_SHR_IM>FAgiZ-K?re9juN`%A5rooo!}|}ucJzecs2@4;wULz>nC{b@|8KJ!yn#AuKv<1TbFm;&bY9QfGY#=`Zu%MpAcjLAd{Lc'
    'Wxz1JN%QoSG*gD~ED{WYvC4HqY6+eyzFf0!_naYciFV_J2da^)pHPJzzxi~(g+Ee)*L9t0yY!XY8mSNQ@rMFK1={bWI9gT;)(@|s'
    'M~zEdJ*+FmCEsZWHAR6)^1~JKZM~)Qr$R~+j{)>JYL8spSQ{@p+bRF3E}B;>G$;z%1y@Bsvrakk02SPI3>N_B8c!N{9`F->)YP?8'
    '<tf`=-bZr&M6pAvR*&LVb^O0|!}%GDxG#KE<`LRlA1lEc{Wm5OJNCG9PT<aF2&JlmISWXzB?x_$-|?2}lWi05OV6!BLiW4Mwh%Y7'
    'LvalOrl!_16i2Sq?<Cz!habDMKLQt>@FMsd5xt=W$>uG|^VgD&lTzGYQAWcG@gA|}lUhgW1LK@;tql)PC~lrfs29%Xc%%_y93!!K'
    'NNWI21ED{g@HAGXI<4yug`3G^8HlURv6(RC#yZ44^ymtJ3C`4|KLedT;_iuHJz;&IU@ZGx1ceal6WO>EYMF^h>@){b+iVEvwht}%'
    'Oabl|_2-pxNqSAJ5dbxA=1%>|>e=f#<hhK9)W)4LQJn7;jXbS#`Fcg=?FYhe-yF$EPh5nw5J&+6*?FBSfbnVE+apU~$4^*^I1re`'
    'VpW&aEQL})acyUv`3Nt%j#21OY^xZT{)&5DPG@2!Q)mxKH1Kj&C}U6MnztHPoq5;2?GHx-E9JD>n6HX&%vih}H89Yb&g0+_uK0jC'
    'Ctgk<1gFq$NDJ9KAsP%A=^Im2k!#6yU)r8Un@e3_A7I8?O?#-9KVymg1P76{4PG9OErI;ViJjF4Kb{o)=5<olXq5qbr6>F68~+4q'
    '8RZUkN|J67E;&`PqV3n_JhvP%OpyfJhS>7Lu>`RD*($Opg7dA!N+-0fdcC2c0CcL>ox-jZU3&N2ywm*~9Vx};3(~=gIGx~Oq*3ps'
    '5!|cpLZ<jG2Wi20q}Iu|cCZ>skJm{v6?=t`&AP{s`j11`BWNnx&QK~@j*x+tiOy5RK2-%UHnUq@$0Fy#&%|99L?yI5LS;5dVA{K)'
    'p^b~70QSZv-Zkp(z%hUxrhYH?jo8d#G<Cg>qM`yx3&9Fojf<9KX3&>VXfk*m?oHzicWZ`a)1-&l==73iq3=XA!2whUJX%R!-Qq*>'
    'CN9O-r8%`#CLVi!%N2UNiLHV0=XX<G%;?Srr8pUSR{R7PG;<}=WPM22BzGgi_T^Mnk9oxnzXV3SS2dp)q~5;=IuflxrqYx|$V5WN'
    '427Zwk=A^-a*O#t*5SQ4L?FofEG?Dx`hV%&_(&T7&)%FvLTZk77qn*}`S)&Pg8IsGQ>4-@-SJEp?;dEwC3Vb!*=JJZD_@^+ltR;I'
    '2+{9uTdEy|%?B*{oOPMQNKO#qW`m^?2t|jrs@T?t5Wqsy?l&LSuV1oDsnPg-ysdu&llm5gx%e+qyCa6yF0+MNwOJdM1|c|T7pn-@'
    'Y9F*2Ukwf#(~1f#0OR3j87v1XOz`o}V3+_;mOtCEZGP<>^EUzD63J8^WU#`uC+F8Q=vdbH`@>N<N+B%gcrw6cIc3)h+#DV(0mT{U'
    '{4S(g?oswi;%${Ovp9i_c<*Sxnleq!x@8_aCJ!y(x9woop@@rUfcP<lQP(YRxbr*KksG`%e~$599sd*jzQSC#*AntvMDc3{ELias'
    '<(S5ET?O;h8|QkC;bCM<KnM^2)*P(57YN?%F9rtY#vTzZlo$>S39*C89Si?mR|SClvj`rnk6^C)keP+2a*EuZ!xh<bbt9o@ZUuv?'
    'c4tE6jCIbO4w*+tM_}tU<#>iES`bTR4f7?F?UU%C#Rg83rQn^k&XR&Az`E!xO$nKGNmEw(l9aupIedwyY*ajYv_}uiCG!(3f%N*c'
    '=r{0``K0fLvO=})^N|v<#r?C^P5TPk(;d68;FKw1MTkiuO@X*I#*p)a3d32ytf+r4J8G+-Ds<12CKr|0Zy#4)l&Hue821h8d|&;i'
    'MRD0^2^m}mYgkbcpmc!LMbdP0-YWye6LVWpP8t7Y&31Cxm>IVdP+>y=w*eVqR94Xf8}1dQ74>|Dcm<pOgj278h>Q^8b<t>_xEtrY'
    'vN?o#rxzn?J7+F3l1C5G#2^-d_TA{RkIe<(K|1_46B7UBN(tmuOn0cF&ONo(%Ics%L;3ogP(TO18oaBPLY7-<NvbM<OcVhUvr%#4'
    'Ru?wz=&|*c`bt8U+olNji#~4iEI+z*`&`1&n)3@MKC>1k`g`mye#*L@CLgZQqG0#lDiLcHZ1({hh$nd2zh86;9ksXRNOwmUPJi)X'
    '>elAF>J<o}=!mK;n=>xogHJ47#dU;HLLRUas}K+tWgr6+2ororihE2042FVGodvs3aVA=^P%UDxx#kC$iSb)-WyOM%a15N5N24(r'
    'hn1HsvlaH#55xq_ElLW`3gxjC6RAGox6N~4!Jb%ue`?hcKdd6$bNIX|lEKw@leTJQfwmKVb)?vLtm3=53{qk3eo;{>ZXI?c(70Qz'
    '^2yp#VHICmuG*Hq9Bf(J)=~QHftpyl)hH0>86&c-(74T?ix&h1`HY#i|9Zwf4aqe`rCzw3D7`wjLL|Az)NS^+TuzegXdDeEa0~(H'
    'j_YQ?4Wbg#to>~+74E2Wo4Cx|u#?Y*J0uQ}l#;e1VgU?0>gAm;z#_n4_gwGNg^61%PTKx&Q(g?69tN^#EQw~wpg%&Ax#~>8Mpvg4'
    'xY-tI+S1nlJ@<-by7D#WePQ<Mf1G!ON&9TE^cP$RKj-J5(mfR!Vx~VAY^P;1N5?IiW}x`IkA}4k+caDe2j6itoxe0gw9T6hyt6u&'
    'jlP&<ukeELd#}hzFD6}J&4ZP`egk85((gvess!jT^*u{V-kmolVFd>*#lgoo3ii9s1N{qBGIxN{E(?VP<fKwwOAhPX3SgI_P9!e8'
    'RJT-f<ZHfoP7D7TOGI*EOu(F)`8D&Hk5t+>zJ5`TvBVV4+ts=O;xk^zDz!h+V`~Y&mg)Za$o5cF3Ur%C+_HoGO)=!v&qE@@6G0Bg'
    'b7+dNObg7+SXmg?ry;8*STR*j0GdN}#TJx@2Yyki3A@lPsXqM{AjlLCpeJUS99fg`EZd9{I+Ad(JVnZQjB|bVSG!M&d@REWi@KH~'
    '+e}waqv*hP3{$}@MHQAEg7+@rH~~36G>EjTn;^fY=~`)(T__b+l1?(wGJzRHXm5w$Sfe^~zsp6Fx>qYssX-5e?V2zroq}HR(=zYV'
    't#0rol_#UsuVjlGXu~4f5mk6!d%VpWH)RGR%`qKsMi2=jsh{E2ix55fy>VI=SI+{hJ8Kk0JflP`U(N3?o>5pN!#)%p*EYk)u|kTv'
    '$qwkTvAxkUH(pxg447@X2$*pgjy2z~0t|M_SY{o+jq#D)ZbHtsHR~f4apf}>>&V>GDSZVQ2#+mPSZV_RS#o1(#1Z%b)aO*~@TZ4K'
    '323?H#XlH7Y0hA(8&;BJyOxZ7;Yb%E$9bb_(BbJ97BPBYUc|4#>wRJ>u`vt1A+k=oh=bVCWl(df8c>L)&P!5<-o{fm_w(%ewM_m%'
    ';l=g_9k5o2589EbY5gM#DIA6i@_i8TTpu3GF5966m3&t2h9P<*%}EozD?yEv@6A?9(ALIg8oFep!`j|S+kEcxv1CwQ31CyhA*}!`'
    'vZ9CLxvPR54Sem;Pw05v+IbbNG1oGMWBmymM?{Y@8cQeOC~ktWv45TBBHL#Y$j@z;m|?cI@k{x)$8Tz^iv_{c=Hqp)WTcKG`ecr5'
    'N4#0;plAi51ZGW6>ALdsGEmb}%Pj_1zQg~TWYgkBHs9<4)TQsnsGT|!AA%Ts`BDrKrgQQNM;+u{BT#V*7c4>=Q_%3pbHa_gLy^~J'
    'Ch)@V4=~Dt+ouow$x9nB_>%9K$U=!Ey+4vc{c(?t`-a6XJ<`0Efk|I;fTazCxrjQxy2`qNB{#HoO)2H<K)G6R7YF_TQ4z)M^QD(>'
    '#@w?`;hIys?5%lPAZBXI7R)`q7Ar!$MoWj^zG{|GrtQg+wwOCF+FBa(Ky#Zln|?(RCk)Y}ehQS~qIZ?U*?#peQu$@f&fwBdq=88m'
    ';Z+|1@t2dskVHWHNNGO1U8TN$na;arjF{lQqTa>UgWDHjY0a_hU{1J%VRnkP2y2QDBzV>RXhGRXux9DYyxyImu%su-Rcw>`5JJsG'
    'Xf9NMaBCRLXv)v4|A~J$+wT|`Co~@A<1nJ*pMa6n%+Z~q<zs7&z1KB?ZH|pqT)4aAY!r>EvYNW|nHy=1C#URTti^@m=IWe?DoB>J'
    '0e_}k2drK#d$eo7l-*r!3jloWV;wMK|J{12_Z6&l^#+7<d+MprRepCzOelB<OPU{Ap~k}i6Z2gKrNn-qH`kN(thX|MLq6bN^Oh@Q'
    '_!<?6A+BVwy?eSIllh9?QF6XYzv_QT`H?u$DqKv`=y#%MmBbtlspCQ^3xo~#E{!6?{=PjgnrR|k=z4^TWiyw~biw>jztSE0rqCo8'
    'N0K-R!|D}p$T@$t@t(Qf@4fxxcvCO&x-m=FIy>@-JmYjc&5C3H&bcpEHXda6qojwpll3b8BSiaL7xCl;p5(od$Xj6HHW)YFM<C3V'
    'B|{w{r#+J28qjwM#m%8GzT6hArDw2SWy}BfEGAc}cYtv8BREZck6Mn|ZveLeu-~k20B0h;w=~)tUg}GVB030(e1>vZUw6IG847dx'
    'ZX8beqmY)Q<vg;a@-}+;Id8}DRv;z=gtkO4!;RJ13H>UDPM;ZV%!vrxq~bb(y|&joas4r&pw?STV!Y&60#D-Nq%RKI;UZ=KUxXVj'
    '(rZ_l4u}d5jTxTiY7}ZcZ@a!!nsLsBdyq=$pglNib%v+-K?C(SP#A~4#RP>ofgi}E4%`-+qDv+zuEW=6$sO@2Z86B{LvlRA&t&{Q'
    'E%*PV5T(!`)lFV^ui6=p-?Og<sAZpRmVuu}8V8yOm^ljXUlA)$#$4IN7^QU8&zf?MqU0~7E&OrOzBXpH{r~E))X<QI=A~*uaK4HR'
    'C%nmR!-3feF%~q8a@$RXr5s5aWpCC8LzR6<>4RlAum_-zbHx!?A4j@hf_7NtUFeBC{I}~1wug;Z``}{zE~HgxFh%TtsDphqFHc<K'
    '=;FMy;fP@%faL-I9q{(=mZhc|P;MXv!apUGGU`wm2LsdHwKx>!7!UmdDL7{_;QT+np-I(;+^_ZqsBNbc7UTtT)sOCyM+Qnybk}E@'
    'E0SkKd`q6Oi59~}>@Nyz8(}`6Rq_S9&<Rb1#T&x@Rm%&zKJyX6nH}iMJy<;bvlzo<s+6`Xk>x~}S3C9emD3FlsF_0vnw%{xt*XXs'
    'oQXT!Qc$B3SVrP|A6aT%(3vu*1Cc5g$6-cA(hrzod5ciI(=r@YA~CIiO_?~@IvW&mcZ}F#>=@LqTlHD41u47Gxb1gW3d=)|>5|Pe'
    'iH($HU=UhJQ=7$oHsTL@?<)Ah`kiyRFf$;(z%eh+Uu)i(JKOii()QhVg(yTfmpvI9tBGJ$YT6QP-Oe~!eJuBCrheoAR>AeGzB-<e'
    'N67scb!*J^2OuShZVH#*;nOa*gMAE<kU(}i;~a^C)?ic18(wqdyAg<#=9P3BV{#!o)6K)IM41#q)U+Qsn<+3gkR5b4Yb-4<0BL5O'
    'sOBaGZG>@HKMAT8{A7hL+)kYOclr5nQd!s8s-$~jpB6vk`k01ZGeSTY^T-zlV55z$oKEcU`fxZ~S_e4?VhW-#Y&s5AlW67ahd4Mn'
    'i4z%{v^buM_nSjz#FL|EJ$anVc93byuU_qff@|LhhEUlgen5jc8*|07Bvdj*%=H<&f3TKsz|E8^%Kc#&$qbtQMFd!BxwpwAFA+g8'
    'pvNAXFrmTPFfhT)x^5?<Hau_ZNs9#{q8L)pw%IL(i<@hQ-USUEFbCC_(8u;NUIQ~%fKaL1NY9tB!Q7$yp3tOS9XL3Hrw{Yk?n<?l'
    '0h&og7_QF3FJ!>!aYij6L#ID54LW9hDZg(HrYC_@`g6mj!Wo#bymN@}<OSjlHQY<$H!6G5uZo3#AkqGWmF1l1Z7TIy_#wszmWVGm'
    'jwxL}F#aPAq57ZE?c9sPejy++-E#s4DTBT10p<Qqf*m8g-EdGFP=hC}?0S5yCji;oB6CFRCe+Y`MuEMLo`p=NTor_HxlNiQTVK-h'
    '<^%Y4rHQt8ddT+>kI%{+b6}L|Q*0jb_V`mAX?NPXg2|qitN_Nes7_w?W(zmqr?wZ9To=y>!d)sW9(AD_-?8B73`P+7Yv_RC@_s}g'
    'Xi_76!n4g|nZfKNm)@;Syf<NH(%`0*TK4z@`2!=c!6fMbSS^*uxIdCl9lj?`n~jUR`O3`$*@v+|u{<(qb0hHC0Po_kK2n(m?^Wc7'
    'p?88{7Jp+t8uEAnAbC$pf6<WQcbIAU3wm#NxNJ6c`ayAnx_jt+8qO=iYpQpYcuoWBuN;zOBba9kU<dCMH5U~3#Nrm^wjFdaH!W%i'
    '3jCi@Pz@-&xU%;`qwl&pG@O<f>NY!kkB}P3P(a3q2X^)Eu%2^JZ#Vvkkr$s-Xf_7)7n>v%0g3Ol`7Lj$fIT*qRJL=*%E=t5#hnnh'
    'QA=cLmPrH852#lzXOtDalA7#$!D1xMtL6uf6|vw>?)pEsulne@b;l13sF#%fm+xK#W&HKRTDTn2-&7WmJgzlHFPcoNl$S=$c<s3w'
    ';Z)3~VWYItw$+o@WRj2bcMYo+K{O}y8>gc$RYq|{#A_kMw9p&(##Txs)$rc3@BxMlT}x=(8Kh#u7iURj8a*-^nQs=kORl8d@V6qD'
    ';yOUx9@wV>{8%3mPA+zwvClN%V2b&B4O^?GL>PWVa{km`RFx$2jpL4Xw1NRjCS&K5p|kwOUk=6dT=v@zA#NVl!Kn~sf~*LzvD5^S'
    'sRE6cTQd)CV(Z_8Sv|-d^pp5p?A*R{Xn;ws07}ZxkBi)T1B5DEVEqe2nUet0-Ev>)->SX%xWR!0x=bUsL1+Z`R8^)!GJNQR7f>fK'
    'S|nLDNitzUd0<Mn7a|Wo7=`?9J*HG%!^z7?W($?xMQivQeAO<m0rkgg{NYUOv|=-x%{=3;DB<4H_*pf?S1BZEl0Szc{{qp@kJBmi'
    'v{7dVstkvGENZGDS&UM_jmF;GFL?%+Gd7ngomzCE{5kkOh$iHgy3~Q$I0+8K7+SiUSUOCJ>ss@G0q$`w@&BP3UdCC&o@?6nv#J-r'
    'np>R7aD*k!6}~(*GxKBHH2N@O(VOpv*4$8NaZhOer1u#uUYidZX}Hd+r9PTvSw5lpgf6~GUYaeuQi`>hkg`6Sip&yGdPdQQzi7#%'
    '<bcT>fF~oYC}F4D1PN}EttSd>_bsU1WHn<DC9fA}E+~=0=)MoL0$hXYA>lUC8=#S{J31p25sDMQ$*U{Bn8x;52j3F@nIjhM1(Pdy'
    'JCKJ*ntv6#xMb;DF&ZA-6kI<rgG?($E~o01tQqDxI8v0Zl|h;M5-P(`?mX?zUxN03Pc)92NK%Q92%UnXOnE6@=?-cky4mm1EOAI7'
    'vx$&aX~NdI)eBJg1pg7J>z?buIi$9*M=6C1{^%{Yy09H&+SkN!dZ{%anb2Yh%~umPKUo}v%wD>kfHYEXAoDrtm8QOc8ydBN1u3Nt'
    'd2}4U$J(ohE!mW)UE#uyS;~irP8A-#$XKA`qf4hl^k<SYyiUE)2<2W$YaEq5Vy29QXe}#vA%()8Mwi2}1~#9c`PZ7Rjl&GH`_EX5'
    '7oPpN>%8Tkt;+zOBkcHe)0=uKPq_~vEGQ{XC%bfs+%_^mN|ee8vY`6dP>E7_WH>T#lT>Y!TZI`Bq;Bo~I+s~7G!Kri>rSM{Cz+D%'
    '{d%o&v)$*S-&_$iQkFq<EV9F;wZl(Ey<1Imj?KJHuj;p$sCexvjcP`k6^R(o0;{*gIXkWLlP-oUA$0DTPDnIEow9|@?mdy|Hx6BK'
    '9^ABLVB_0`yDue;N49KPOgv)#bHz>~Rj-HHmm^1Des9PBpLY{%bIhKuI>bJG59+n-HjvXMS|)ouUp6f~yLy&Ol`}+a5i)?+Vf#|9'
    'einePGoUDtC=*pREkE8300EY+%}u^qE(mI)!nmEmdlpu5R1{jR^cnqQR?kdl@a)aiw1-uPf(&5TAh<prTM@A`ZyqrGn=#Dh0P=V`'
    '#!Rqofv+yFES<$CxqNN9fS~TvgkzDl-Dg0YRTvpahei&)b*m?Vd}_#{WGL(SCI`VuPh3WY@dU0$HYh(gm)Ur3o&o>_K0`cl@U5Te'
    'Q$^EnC)qHmVr7|8c0U8Ph@_3D6`Yzq&L4D4uocs}d_rwFLM0rAJmeikgq!EC2~t%8GJJi`N-lZXfj@%<uGuHU<aI4U?NqCS-ns<2'
    'S><DFXE4c|nMzd&l~2VzgutN!VdEja;-M7GY1<kndCVZ2v_wU&EnjkP)aXE@Kl+CEGi)V9$lH1ZtV>GyrmJR2x|MbtX5y%^;{stK'
    '1_KJuVB1#3p-0skDd-8*iw4y7JMyi`K%8W37CoG0WF<H|!>GT1oOIpP66LIAY$P@f-ARNQ6SUga>&8%I2lmH*2c5hPGUID~8aF{v'
    '`5&1o1$FHVyRa)xR^VnKVnu?0G^BVvd<qkBK{)j(^-l4=K}wF>4Kro<|0SMvGHb#V>L`Y`(CE&!;C`&CnFK1owYjCFI<%RRr_Zd<'
    'rJgt&!kN4l;M;RGp^=;oSZn6RfmRtC`%g(&?lSSgPV^-&x}Ka^JSCG1#ZKz5J?+Ad%DP+lb_fUu`kPLcBcVKn+9)yJh)HvCG>R&`'
    'YD`ibH@VxtYQ!Ik`znX@@`tJmt2qX5N|^`8Vu%PYjLOYEe)f%Ak;s8uS=S@?frcR82v>VUq0r`UqkCfFq^dpuiq+!h>qb{gDpS~H'
    '61p~<0)Z0*0?+a-x(lnDtU1h2b53}C;cOY%zc*eJ_S$SfCaE-M*k{X9HzIQJ*{ZIqx#vf`^^n>Xx(qqyZjXxqh$}fUbcGNCSrw@X'
    '{nA1LH3a@54j!C;f*er%GgEQ(3Lz$@X+BrmAf5s;976gD$HmDG56bRFs(}fF9TqeIY7@lA_!)Z5x_$hYo!^`$pl>2&f1d3fJV@S$'
    'sJB6~;m*9(s^SN;s@l*o2G2SKXSPi8yX{;Ls22w35<I~BDlaHuz}OobwLr_uCNfII9`6!U;>OH|nAk)4!Tdaa{ZT4^Wi{xW_pqpB'
    ')zE=1xf?V3(UP!h69n_eawXvX5*OEqHe_v%Ndw2gd$pHgurJwh4f>Vl@_1^~2Yy~iGoD(U9ZyT+$cY~J{=Xj~>{el^(_HFOyk%d#'
    '2IFrSCmgR!{p6Sw73f)8QIHv)!U?ot3Ir!_QKE0XI*M4NQ-2>dgR+Wu0c-pW5$1zPhz<9LY<OsJ8wgDK3Lb)&hnIZ2zBSDH!Q%9O'
    'Q7%|$VBvsD?Y0aU(ICxZr9vT8Rx_Pr%O(Ck)w1(*{bCUo0JlOqtgYbSz`VrYbN!~v@HH~`6Z7I5t~bA&N2Bp9KXoAN-6?06U<4|#'
    '8*$;_oCdG(1Q1=k3-0V^9s{k}N^tRbmw+p3QiD#rV9S+BwWV1<pW-FK2pA(cB<ohyw~59)ql>n#Bmh10fII@&cO6||Can92Cb<9Q'
    'vz#^W*_@8^ijLKzI_<^&q{N4b_eJ{EfV^$TUM8nA6cJf1SYmpyv8fyE^64z9TYkOmjL5-9{KSPPgQ?Xu0HQMc)huywS3l%;|Af<w'
    'At{33vm0`3z$O{`VQ3iT_1Rt@nBV!m`p(gnu-kbHEEl9>54i<S>meDbNHl(v;28D|aVtJfmti#?Oq?S-<efetMdDgP;VtR-UuN^m'
    '3A!%&2%iP5^T_YaMKC84$j)ha3I5n6+I93iAxWLo$n=;!0He6cAH9PYvU2){eXPrz{0;&~_#QH>lap@YxowiB%0t_+^k^MqrT2rR'
    '9lfKyiE#gYX8WuY#yrnPWL!QaQ9BSpY#DvW(QFUSE@~|1vhfEyGt+CnD&E3Hmc(`JD;R#SLelvS6hAK{4cc+6!lh2N`-IaDq~T2W'
    'MY4ewvN{BCO4fVPQn#O7?CX>B3=6!Rej`k4$OQEGSt*GI>Hps1tX;lB+TYQLtR5|ueywtCL<QD7t{NGPh;ys=W<;+@aVaDCS2bdK'
    '3l0o(6AI>D@}TG7R{i}h?^UDC$SzQ2!|@<Lc726xyp>qO+O`d~VR8d}1KecvugOZDrX>!yLltdh(T=HY_J_p-^iR$?ZA{qHg|3U2'
    '4$9d4;*l)390o=45)$F*?N<8L<do>onDqWxTY0d9^UMDQiL)Y|l^t^6lZ2%w%0y!wKztrK!h%MI1Eg2Mk8fhKsis7k5oz6r8g2@H'
    '{N^(Bp`@zDg-8##Md@U+N&?20g&RSAHZ$y99ESmL6^<yrUTykpBK7qoQHz~neZ9$paA0DYArI$9n<cs1s`V!PiNd7e>N+mcUeO4`'
    'Q~dwo;pDeYPID=jqzJ~iQhG=!1FI>{R#3xl&HBgk@*6X{f|UMKD)m=YI5!z03Lo?ikfmW2pHQ$dNr=(x=7`#DxIPr2EQc6qo!QnN'
    'YB<-E{@f}ZLr%!o?T=D^JeKCHnw##mG{?hG?6+K*oFaylIo|XoOcwN7?t*v>+;k*!Sb$dmaooO@;fZ=85O4~LwL#qOAob<u<}Hk='
    'Tze22WBhnw&Y+W#{`Qs{glcP^s?TfaS`lKp+(qS-0>m<<0Vi+d3BS&XND<!8(6&Mcpe4}TunKZLJGiz6Z5qEB^$&1dP9^MwRY@tj'
    'F85jzaE0@%p}B=6@VilDiBnE@dJ*S0KjfyD$5&>3#BD_2%LB%4od<CD<j*rpl9s%R>x>>AHgBCTX}i<wT?-fWSOAt};I58URZSg8'
    '_c&;uo%OJ|K`DXOAe>ac<9Zyd+q!t#6bLiv%2y|IbdD-(^q;<Mq`?Q`9N?isLr<n(J9~*vUy>}0$(y6rD-3);kKInFbkj|HogqM0'
    '0{5z68Q8^*i%%B_RV343YN^$R^}lBSdJagT%kkX%2MlZQ%1#JR6BQRBU?ZipBN0x|s*aj_1yEu!b5mRUc16DdFm?LBjWFny2*;~I'
    'caL-ddYv5rjWn?8g$#1hC}(9K<gMqEXL1tbUF<muO)TbAQmnOl8pSxZWGbG2YSBOhn=F*TL)RPq5ZRLq(4duO+mDYRhO<)1Sn%9c'
    '@bh2xbuE2=vx{ekTvTIZ$M)``AUb|uOH5M-1M6#}dU-^f>=lVuP57B=O12ja0IJ8{lHl+VG%C%xEo^COeP;PGXaoYI{RR>u2@y>E'
    'Ecd+f*JR)dYm&cZR&qOsWqRbr<Tr8Nv_>9|S&ZTR%2?C)t(c13;|hHJ*>;RbB8x>>l`!n3LPB`}=vLr+0A7F&(Vp1YQXf=8HcUQk'
    '#<m$8r64hXrO~w|O@OyNAGmYYnQ<>JTCRwFZ4kV%f`-IJ#=!X1_JjSZUQ8M|&1Q5RDitnokAN8C;U=z!$LCb&GRjbEZ1q(*%hL6&'
    'k8XSyBh3s;eQBYlbldsXVW3ZB7dwd&c#fmT^)3|s{XwGRPx=1ECkF?g$Kyo8!GoT4yX9=@g@_>cD`eI%qpe%1y_TA#FnR6d*!_WU'
    'p>qI}@Q2)F`34zeQqnD5>u1q@kA!B%Nm;i+FhvcgNvJmEA6m7c-Q{Wu!n*Ub*|3wj*Zn+LyqktBmYKgX&n`Ts7^z1##$>y9Mr}lC'
    's$;t3h#44Dyks_zsz(NVg3`q?$D=WrBLMyh{0zZd(^`?k1^e;&grB~60y&oB8>cWs`c@~nHIXQ*$f+<{f@rCU50*&h%r~euN9Y62'
    '%U?dy?X!&o`|A$R<V9+yAJTnp3~h%vDv6*iIwgm$yb#O~v`&>>4UdCb=1NiT>MJFPpUbrDX}%8c{FBw$soGQgU^JFHEEJNG3ue~f'
    '?i#2R>#PgEm>ep(Q^B{nd^&YpMM9+_aFDvUqC^A4Z#l|cvs?ZOoW6Q`Peei#BVxnyP1Wq{AEqoZ!r##@`!ejO)yv9G4q~S6k;I5E'
    'AnpSMH|s}$8Qw01ru5X%&jf<k&;+^SM$xa}vtC?Ln>M*z)&UkSoky57D~4U&In}g2F8?8}>KNPN_SKA*lV7bjHw+jss1VpPqkxS&'
    'WZh4)TCW7iWmp8QK9cX5i_cDP+io?)xdAHfCU}k3eYcM1lDI*opK!`6+4ZX`0=c?v6#t(RhWnQveyLVm&j8*l57ViwP>W*5Ux{#<'
    ';zlLBOXLQ$;H}xlX~soOu+14eS5VrVn&PW)-q0el0^a1Z>t`F;DR(&Wm35}`x21vY<MvNELINnv_XtN=Gr^nyfiRFyoZOoG5+u6K'
    'YZk*oMOu{JF#^5{pC7e(JHU6uJod<QlK_#&2edc!>z5!I6-tzfKHB}kQrh6UVDVQ;vbOz7&o>W6Ww`#It$JS7{#A2DPp2zI8o<qg'
    '=LTBpzh?3Y26&}uv`x~Q)5w$14YZ@18+9EyBbr>W!-H5)>w~gh^OkE#pf<ak+K;E4L;1h9HL1#@75djdh$;ukuZ@A?7SdI`+y>*x'
    '{H+dGQg=`o0rO}<NgPwfFaInnKuzMoDKPz459Avso^uJFbB{4Y!Y{O+3K8L_rojcF%rSUm2W`pX#^p1W#PD$4imim(3QwgV_+g@w'
    '(0b%`wKZH&9p8KJb9?YIG;g&Wb1&%fz|A~9u~CgGX8LVexMj9Zl}|3Luly#bAorIL*(rB8NRM?NpCf_pZd=lqjy=?e3DaH<sibpB'
    'J3+<gl{zm7K>e3facT|niCh(9`=vuM-GbH6g*FBmNUfd;QqSv~oU?-K_!^AFcusHFl7pRA!u(W%F}mLn(t#v!CC~_(7ZVWf_$+9|'
    '9a{h@s=&+<zZ|{O%`(dzv4oCcN~z!xJ}dbf2)gIlLv$=Oaqg)M)(=qwOKhjuStWhvq)bm8c<#zd&lQPt5j=r9f2U&4I4INQ=LM+B'
    '0Zx?a<!Iy<32owNppS(I7ZPsP52^-p9Bd#<Jc5T5lB;K2sv7R*AkZt83ou_P-{V6)4ct<(uAp<bH~(X@65QQ!ObY*Ah6{eRxpjd>'
    'FEKGKO9Alho&Ru+<p?yEDD&G_k7k;acix<u_rB~m2b@as4`rPoub!6M)MdlZSgm!G2}t%e__0_RARa&<c;e<o9xAlEUNb9q$SLmJ'
    'xHyx;=;(XSnp5c<eMabslx;l#WzM{Hk^exyon|1SSrd?e$FQ3jV@hT#+n|hl{Yv9^WhW}e+T)D|KBA3v`C8rZ^nabBXc#EcU|Gdw'
    'kaY6f!bqCykIR!sNi9;Ns#hi^J8KVK1amqH?XR=RAK#B?HRIJ#dV*b$qv9s33qgG^z2RBy1ClQYkZ_yrSL*lIR*4O_{@F)9sVt;#'
    'FH1ZrTElhCZ~bW0?JI$~w(am`dKV?>a0#0;(AcmgjYR8pwk?#2wN7o@f^Up%vCi3n**l?0(=Pr_lTYFuz@TKQq@c~g#4I>wLjKaA'
    '`^=Te%tInxaUDPZA;MQAjfRNVwjG+~#CE@7Xo&;$BPe-CJ8VtoAV#T&mrSKJ48M+kf5bYFxbi7u58gNTE8P*Z;k>Q$z?&@Al)_H%'
    'Wa=-Gk&jEOM{KNU_~N9}tH2ZAK#4IdBZ4P`qF(d&GofTwzdlK^Uo<1dw{f5V)}*eHem<b9It{^E<)${OteuPyT77;)LnANb_dh4;'
    'R8i?S_!{I**c#;Bza8b+kAhMOb2PM6q+!W`5Hb&SMTrg|Fx*;E#(x6S+DoEO01osS(;-g#(EM8j;p{+Yhd#nWm@${$vfTEbm9F)O'
    'Kh>jMIs-E2Yu}k}DA-iPdp^Y|AFA5<$%2*{?}5ec#JEZf;aC;R$6Kz6Jw%bjUc#**P)j#$E3Bdf;(2rX4vs5fHG_*9EIPvSVuIl0'
    '8xdAqS(7?Pm-4YA2YUcT--l{kXSCn0usLJoN(oHt#|3!!jsPw{ApT`kP+T9|DjrC07Cb29*k&6TgiybAY<XVmUHR3WuDsSswLv)a'
    'xWs5VO8sQ@xp3&-HSoX}aEjv_<4yJ<z6KFf*dJqWc-M5E?|J8ZoiC90rK``bfq3^fgNhy>n+y)gr{t<s+<q^-9~T>|(K>F0sNwTu'
    'oSnD`zqu?!cF2TYLx}6JCu7j!BDho~6?*Vj$00k?49Rai`Sn&!g_;yy)FE*LZ(*o<gA77q=v>J8uXeNl{%H{+*F~C~B~a8C8$bkc'
    '>*(Xj<EMuhBdNbcF40z&+30{QnD2(xR0W&Sw8^t3>CMJW5gk@$ife_=OmYE!1I$*oBo^4-fwn@Ds|5yMjw4sX$sj^RzkjT~q?_&0'
    'ZG~aT*N?n}NWDG$Ghrn*ae6?Vwu<UXTJ4`=v2BP?T)FRl*F~xT;JF4z4mb6BG4h0Tnf&HDG@@=`Jr33^Wpt|OE@rYA5DoNVlG*nD'
    '{oRZ$7g_zb?gxQgLdZyY;e;iq_`PhaVK)$qbyS)R+dgo3bPER)yghrII!8Bsbq(U41oziO*`JqRmJ0YJeM}YW=jXT-My5!~DqmiJ'
    '<Ez^$VZ;zH5dPpC`sC|w)oR<aD-p4Ph{Zu>;309hmD&*>ejFJNA~<bmZ5+Tu4A9nH)x0qODwMRR&)nUgjpp>6P7Q~QXgg^)1C?1;'
    '6MjaJ4co!s>Q2_jTuE(3$NxEDSL=wj*5pLr*4FWP`F8R0MiJxJi<H*cXUnNDjCogcORdZ!XvnMBL_c+=0*?Ux*@(}iFLPe@jJHn4'
    'jp@6o{H?G!ZX{uj4s7Dq<OoP5a1rjSMni(2F34@%p>&y>l+g<!AZ39Y2;U&jBkJ~{M78QsvKGlDg_;or9Y`yH6@3iz(|v+tNZ1@F'
    '<RO#yEY@u-VDE8%y13VW6rREq|CHI@J>9IQa5sa(Z<e@?=$DnMLx-W13hrhh;v-JyJvc^pMX5WooC*{Ne(+h6*S^Zc;3Ap4z9j#s'
    'k$;M7QNdHSRr?<EA5+7tQl$S)c3cgbz!Axz-c>pRu``bdxZJ|UNAob?OmfueiTl;o@E)wqOrRLAO~}O_L*5h{I##j^ok!Nv^}3{J'
    '+a^=QUf{3(?DffI+ec(4gwlQ`NJ-NX`eCX<H*?j%?wBt3_!gpzTQVTUJ-aoaGOU|{qC%ZOWoYH`u5&Q|<<3N%4wwi-W8<M}=oLWc'
    'IVJ_I1FsrzXXQyDK}~|?IiMJMm7Sr1#*@q$bMU*H3#~V+E)s_H!8e;BiA=r)U`my_k3?1m5sNc=S5%EkBW*cQ<~Gvq5SNb^xQ^)('
    '$^P${M#x4%$0=j)0gu|DyPZQ_kaWyJ`?)D}Zn+zcl(XkagAwts_#V$GwdK=2n*nPD0Vbr%pfON`oht$wmvb1k2=Vo71yS1koeHHP'
    '|C>lwNu~`JTfl6Au2WD73iS5*>;cNFvv;=UjP-&{^<>b^KX=1Y3@d0Kd~mQsRiHT*BVYxE<JGa3Oc#+Zu@;y2kz&!j&;)|gTIlur'
    '+*SoOoBkWq6$h34#L}l3p6I29SCXOs_<axVv|DQkQ>!nzPdcn~1TiM4?(Gnb5L<^5QyMp(7}0E+5(^K)*2-z^92~5l0aa8|c|@5B'
    '8VN6{u-(=Lf15UpNkAm?qWAk0_hBG)nSB>ngD_v@IQbXm#Rs8Dr_&nN_8pJrlmvnT90A(F^vDStv{^SAENhzxns7J8d!+rH)>Wa{'
    '>788X>`#$ojAX$}qaI8lA!ljkQ;1CB=thafzw_Vs+~ErdD|nl<olAP{2!z>K8LUEe21i-Hpf6NZ*&<{KR<42_RgzbT4}tpFd^dDS'
    '+1#lOk@dUGHUaEp=1wx}qj+RlnM-ZUOOZCYajAul4gS|DSlk!Uq5S>{ZL+ven<9bRTocGHPF$YG=_F#{AmnU>wc{3(&wu)EgIU=!'
    'bWjo>{j39oztnc`uwhihnPvdCI&g;e3AYhu)I3Lks{nM0!*IOr0<GQH0{}ZkIk+ASNsWkHxLt8jWf2a@T+3il<V0!Bf7Pn69RPqq'
    '#fj3tI{hs4$t=yyi&`y|DLXf~USRWQy@t@n$heKrEOp}tL(VWR5c;$&12KcRoW{Lc3;5WR8}{Zfz{yVg%Q+ID+BXI~hAj+2lcKN}'
    '-dh}ru1`|?AbXbV@;j}!{a9cOPp5J54$wEvb10O!Ym*3r#BNl%N~h?+<L$G|Nl_`!po_Y_g1rix->camWsJ%7tQvI--ya_K7RUng'
    'J10)J$r#f2O3o1_mpRMSH9;}e;7i7-U>I4nt&F7rkkc)r_c%^@nad)4gx|jLlIT>~`U39YJ9jvMQ!?Q*Eo<<K>^$ui<;zYqOVx5@'
    'B$IdyY10CQj<DG~9Q4xtStN60$as;`@<9$10O+Eky#d{G*3;9oxe`3ghEkjP;rH|Cpohpe<(9$1{#`N5?<zA~K4@gJFS;SYDPBZ<'
    'B*Ikut`NnPEm6eja^gkJZiT9%H=V=C_5P6oKSk%MKXe#5^}?)gDvI=r-QmO{jkV1>K`a*S#v$lA^f>*Qo-;Nz%i6Gyc&@HP1j-Iu'
    'rbln-$2#%p%BHEq=>g>9P>!iDjw)KJ@<xCHNR}C|cEM4$5|{yl-JsmQ)J~fD|9>qBYTUb`*AiqgIY@`=7ZhKK5bro2ufAUC@`VbC'
    'jLh-OUJtZ`>l}&a8^!Vja-k|@GxqnX=^8kGMf_{2w?qmYdLjPkQ?mLWu&3>=5C!mWO?(-M@E7>dA3^R*9tAbYd=e5~GWmd9-e0A1'
    'F6$-9N6ospAquew1@?thnoFnabh;5!@Zav}tx&8N3mS|KMN?besrF^Rlf|7<W^^<T|E|3{iS3xAae3>PB2t(MsqS(L$zm{$9k;RL'
    'mFJb>OM>P9V~}<sa#_AUPT?HYsTe-?nl;+~Ld{-OMP(H6$Xb$znR<+!4Tvvlpx=*fK12#XZKx|#v>_&5VswmnJGp8Rt~e-Yd8un$'
    'c3`O4{>4dSJ`96cQUa2XBjsw9FNI{C(g<-sVk#Ou0IUceeI^_MXWNaq5ghR1wNT6YwB@$Y9-><ddcz=5HEAXDeQsj_G$H=M_Mg2e'
    '6&yx#*-a{FOv+G)+cdP0YWX?O-Nk}tVRCmV^|4Aw_Cw^8!`>I$x8W%@w1WM_Yg)>{TaSKiC%HLjVTJLgPR6o;CMCq5rJJ0b=dXpv'
    '7mC&vM@554nOB}|-vDTL%9E-6&LE_e^l{(bvBL)~G4q58>HN4jeJ2A>pM4I^gT7OG_*dsO@R3ssn4$1e#U^fXfLGr(I8|0dIZ565'
    '7>O}HQlO6rYshG=vZ9m}D|K}w2`mz^+|k#}(WvRyCgj<E@skCY)={Y11$Dft7VHsKQ;Tc*5!2ociWs$>rWG#1<S-J7)0s|BTT_8-'
    'D3+`SxKJ_{Cy4?$FlDTv6;_k;Gd?KEmeNrELRi+*H8dUlhR(7e?#NyjOS3J1_pc@hDPdt-sH$TVI@a*JhRql9sQ$U+SM}P?9Od$>'
    '+4Y&gOL8m^;|Fx?2qs?<t1fc7@y$7*F~WcwyU(~<K9*}BK)VMi(5s{obDx_b60z`iHRJ}Z$$7zid4dW0;SF<7=A^E<!?XpybY2Nj'
    'Ez~MVHHan$3L-;43Q4|MtwJ}s(5jEmtFfnZAg|Qf5?N>cSGg`m!h99?RTn7U7$se#7+sCj5A>I|C_vB9CLH|1b4dzjZAn#Di8*fH'
    ';3q^C`2v-cu;WefWbn0l^Ou(+Ju3%&?g%Lg5*GVtx*kE#6q+Z&ygW{Vq@74-$0Or+lhlEClPhx~8PD+JYVd|7b0Il?;k#(*8`Q3G'
    'Paa83oI7s2)X6F(t?&U8jMU*dG<8j|09`TWUsY|5L=V?^3Uy`!*$1JVf143R`9|ZYKXs}lI8G2fP@JWkI0d7X0V20li|udU^(Jj&'
    'p&<jU@n|{CblSrr%Eyv*)wzSEmzTT5TzOWD;%be9JT;h6E#K|DX<Ob!Ows<3eU-OXkm_OfyG-j32XyW-X26>IY0!l*gW~@sx)O^l'
    'IZ>Pw9@RN-p&kw+$TT*O9;GBmZeBH2V0_tU%tnYRF{NAB9v6MnwqEE6t~PhXU0ZLh37Ba8nh|>i^|AZaQ}M*UIZgytH64=?TT00G'
    'q>*R1e$3q`1isW!E|U#2c3e4)3Vm&cbrd+a(rtQsl2_Go0P;LakVYnaWCvcS=D#14`@C1g=#7seuAMF!Gyz4yzXJoW1OLEyMLpEy'
    'yrI(3gs-7?QoTu+Pok{73>y`TpvNDFM7kKm%fP!3-->}1Xe5ZEloqz8$7m(LY*NLY!NWr15GV{$8-t<|3zaO@^hfE$Y63KqRKI3W'
    'a@w{6IkA;%db<+C-PigxT&8AP8Ft1rm`rY8o9hne49lHL-1*Vjbi(Z|!qSx=Wq9l3b(9m47uV<BWQ+st3JKzOAFW&*w7c_!UtKla'
    'rv(l!{EWV5V3}-H7o0`tI+UTv?&Ang+z}yslj(l_%LE^TRYFs3mF`ez1HjR@oi%rW>S-6^^eS65X&oX>uM<ohX2c@lv`I@W58|nr'
    '-ReD-Dpa|nwH;r3O^u-IG#V(BN<aB9JjM5u7okPbAyz|~2kt&Zz`Bp>c>XL92bSFuA(5UPIl-lC=#ql_X3ol6-*%+o?;!4HP0PTr'
    '4Sm+g-JQm-L=iWP0u7%eg`;AzkL1uGWv89rilT<|j3Ez)6=L7qIcX4<(#lM$w^}sxY56_gdm=IEf3;=)1C49fl3Buar`Rqod28wS'
    '0SvYa!3G*-8I6_pkPfaH3FSD@>q8mb`cK!X!`vM>-BUtN#~#kn(Qfy|DZ9>;9A!vE3<WYyH8wIFKpBqdz!oMm3v;M+81N)!lRW%!'
    'xVknDdO<$p<5!(S6KJ5}@Rb;UtXd)z!S})rd|M|TB9uycUx4Rm%pLtwiIEvFJLwIRm@@RCOA|K;EGiyZlf_8|w#e>Q&>9zsz#rec'
    'UU;OUg{Xij5(91c--)xAm0!e#?<o{y7@F&$RGvP^tJ4twNE8koI+y#DR!pc%u^D*&rd1VgQr#=iX12}Q-QWk%$<hqQ=H9kOv@v33'
    'UP?5ExAqTZ%M1P(b*uVf4on0_gGLx|Zub}0pcY^E8FurzJ&8uk+An|1&#F5k>u+%5hm`@^e5+HCBx@v;MrUIn#?;DYhoaR<E3=w|'
    '(FI&#YECsQks%mFFEV%Asnh^vHh(3RLPNbJ2l67x3GaZ`3!RpD>w!~(UGCzc3lR*eb1lyuUHyB!yuT7`4VQz@T#_*94k?g$9!2cE'
    'G=Hz#7ULJaP<}notQ+_nnS`6Y#Pxw!HS;O<E=FO=#Cge!S+Y|^o!b=Nb!)e77}1KP9U!J<-A0$c@yij#kpp%bSdy?&_|eE@5>rk1'
    'eD)VGvlVb?0cK6Dy#Mz<BL2fROH~tEc-R|}@D>@rOzN_q<6wswwTMld(gIHZP&}CvTm%d61Ge_p6CAVgFO7qDvvx+<AcUoA^q6P4'
    'YOT(~zChv<S5F$HG>-RK;Eb{0i_R6S;V+*KRGFpWc%|cpIr#e36;zPj`#7=QRe1dJsSf;v#08N9Xl^f(5@;pm8n7dTr1GAHO&n06'
    '%9BbC2Zw~67*(L({s40&h~GWB|8X}zK7R=vFp)UY@2P-<`K9WAg&}|#S}25Ox6dIYqn%O}V~vee$%WS@MoXrAVs~3}Thdi>ElpI#'
    'Id0w}hE*p-T7;W5jWM3hS}+!tglxD!n>fb7cqgWzJ2~?2Fw_K0rsCIMz?m(Bw7L?&qLG0>qrR58*79MSlaj(NoFipsW%{m@T1R3@'
    'v;%JJ6Q|Qfvf|vqUH@JgEO!=Z69qMV%~t#x_Y}j@FivRj&VrWt0R3ZQ61brTx}3Z@uj2R0c@7vS3*tDHDp7reRdvd+hvHm`L<EOB'
    'K~U=H_B67?R&(xS%`nh`;XT5jVjWf9kj`dr@>r5(_{*H+-hak`QXV5v#`pvS3y^n|hls>}!E?RsR+m5!(^19OE$n@C!kUb-^ET-@'
    'yd(|?@`=2-OFRbz1-xX=s0@pDms)7?t=<z3B4B)QjNkj(@0@OR$sau#y;K;N*`tQor^#y@qlqundUgdk4Eg;!Q2yW3Oz3u1Kh@3q'
    '<Na2aK+k*#5yID~>F*iG8SH_A3JBZdeGGV{$RT8d{V|zd+&`RdV|{q^eBOZ0mEDX|$;#3^f;OmZT<s&CIn1-PvIs+k__VS>DO+Vs'
    'D(059wagD~@xq?bHu#TBTOu2JL>9yY&KM&X8Xa+7$fV%o$SwY;8nazLJK4tASGr_g+@4{LT9{Oa=#LffG$^=U)?2RNabXb(V$#WI'
    'i*M`n%r57H#<aPrF@tVEdn13bzcsBd`b)Eti6oc8^#S@emfy>}ARBgFEWpF%7m~+nbECJSp&P8Rdc44UOg2afybE{?Zuvc_LD$c*'
    '&S}U#J2VSmDrs^rviApBHJK2;>{JUlI)YeX9^7fRw>Zs}xA9v$8<7mq1s;xKT}aw^H9v8sxKB8=*8QJWGAn~gUD9h4+uP!1+}30e'
    '&BLm+Db}acj}i6V5s2BI1o8(tv}BJhvF+=%i(dqMEQ=*Qp1#omDA7W;-ZRQzE%2}w;x|=@Hq|Ck!umS0C7uXW_WScV;7Zq;R~d7J'
    'i2m(7S>SL(oZk(rI@X!6KFC{B3CFkFfd(a^Dxxq@p^%~=^{7>Z_mrU<u>6}yJ8=}}Pz}LjN!>@_I8(X1*zK-m^{`K?YH-eeu%rqH'
    'sDQAqS?80sQxGW3ZOJbd_5q~S71pc3NsrK;BbLv`?2K357X!VB<0snj^&+QUEn(E*?U7H8JyrX^mh-R(d}14}xzodKA61PJaYeOP'
    '=aPiW(^62`#*hCet6SarQF_0jeizC1ruc95Y?E!^QZVn)ZCzTOtDscqia~8qXA53&H38PhMr)bYs^E6cM~J-JVOmqcw5h<(Iu-HE'
    'ZuCSagxEbM3iiK+KE#EAX@nP`)C;zTxU5>w*qp-zG4M_0_{gPJ#(+BrW!5<~46SWASXRGqXSL+9_kg|#(uN7(SwCZb(4qi5jF_Lh'
    'o`oi67t;HDPHwQ+eds{a1l3}O0XXW&BTg60Ii{m~fmlRYVm%*7iZ3%9Zc4Dy)23r96rk~v&+o?p){93pv|-zPJtWVnyiZDf;($}X'
    '>lk7GgMJ+u@4Jv6?~yxCTq81e4|J4*n#r)gZAml{2OL-uNr1)~Vv(HPv5k|vTj=WTx3{aTew>(=nliU)Z$HB2i^sWrFFUaFy}~!{'
    'xMu2a$s6ajqfw7dcJJW^I+Xqn#Iiu-#v#^N6E0(_tkqybiR|bMbQ4L{%we_oiVCq7O>Z7~%tH#z=1(7s(#jAb4SU%_vBxtOvE>!Z'
    'QYsvpRs@?Ly{AK{Q!D!-Pw;GC6u1>)l@V*4hP>u`yGdQ0fg*<)C$&V!r;W&u`xgfA(9SFbX%7@}8Y$Bgff1YfS2r8m?d`7Q>bHeY'
    'hGcEv)B?bqLFGY;W$UKFUjzD;Au@V0+5E`z^lgkX?9QOb)u#jCUfX~*w4-p%x|t5IG}Bw~DTHbwq1q+Hp+liUOcf~eL!KnT@<dUu'
    'fAp^12Cgw|FQiqfI7$ZtSKYXIC?gpj21x^KODsbR5OOf;s-Bj!K*V>sJ0JW@m&^6!S<xSEp_vv0<SHc;70Gh+T16VU-L)-y;l`P<'
    '5V6JKWZF#+BOd^&CIF*u*>d`jL|cs@F{p4CHaNE>zq7eD(yi=n+M+$+If`6)@MGmn1$Sn-P54&|m(62Syt@c*k!##cv?uzJYfV1p'
    ';r4$#p1*Be3s~s|A(i=n*wUUidlkr42}|~n1pya*B431eLXjd7Kvy&i>zPRJxzcs%{+1Nebe5w+zxq_25lS?bJHlr#j!SpLX-e84'
    'BTW0g=b3CMR3ruvnF$<{lCjE{c;zPv9yBa5y$OFH?a^YOV9p{oPeQ^z3!H5Hv@nV9G|aNVQ_3!};GTnIv2a?Y97QC8QI)wEtMkxO'
    'JT-J8h&NJIVSD<lS#SxD36<7M_ERPK`-m$KH;UlZWs99PV!bgMBjL<JfZmwRZjb?!?<PUg+Ix`#!6f5?+~pA<4UWuMregEJ>foCe'
    'Y|b%shnkRb4HeR8F{cX9pKLbUL(5*`@E<%L{;w%UxUm@Oa49|tYs0s3&<;<Nhfk|bz%WAbd2q=56f=h#XCW+_BW!`6!Vw=cc^6)W'
    '5XuIUOg9zB0mr`f>=d3=OrPhr2W9zzf_OMPkY17Bi;;HU-m3CFJII<fkw+LER&CJCDNoCJ34@-)P3s)2fDkFbT|8ek&n*G*eXX}w'
    '(I35B>O^%vF(vC;6$c}Ox0=<6N$5uq+mlVp#%PiQL=rOabAbh-cnoPkZ3cbN80`F3wQI6a(D!Wh6erL<4t~20_eEF#^lGVZ5*C8J'
    '62laYP(^50*3ZgtScd+7RkPdL7Bu!_P+`p3kIFkRX3~>k<ik2|70JK7cWDXL77egA$wZS-SgDZiQ9kf(<%rK}LXn*+)b)d#9X^U*'
    'SqoLQ5TTcN&yn@p>T2|DHY&`(#d?V#@<c#eMV{=_N`#&qttw<|MK--H`Mv5VSeUqx6Av{Wz(y@$hIoM?y{@pdw^V~N*?kT2HR5FU'
    'W8&1XOy)*4`|rkf0<yQdzeG}mi;k~gP-GVwGh}EjFzoMp=$dG6=sEtDMN`G!eiz;oaZni;!{ypQALDhV`@Heyqivxe%D0?p2jOX1'
    '`X`c!)nrnB;y1<5nb6Th?TW?)EWR`{i+lC52SCd9@`w{NGH{|k%;rKou`M~YAxp=bktTWLKB6srH-MQ4UDOw@3Gl2w*z11CO(cBT'
    '>kOq0b=I@?S!a$U7;vw(7}xFvCzZ&`p0`(UVs$hRmrQc)R7f`q|1mNE2O!J2>jz*-pA^aMLUzyDXXDv*>;t|WhfRY`4d|Dc6DR+f'
    'HUg)=Yb*8cPp2WYgp}VqQEa)?F+(?-zj9P-&W73LxkYT}ONpa@06tjvf_^w51d*}YZ%m?O-p)w7USO58IL^c;t2OvZfpnbDjUdM6'
    'HJNEH8Cy~R=5uRq^s50<pSoGCRXKjKR|RxwZ`)6?(<#RiOpZp0!QP4tpBc>Pe(Z%vl5EBUmaB*Q;?zl;nbLA)WuxJSKSULs!VFjL'
    '6E@iRwO!#6HGnxtg$-1;adKmMTsffwk^gEanAC{G+}kotkRna9Ul;`(Y@{Gv{IOLz1|l|pcd&Jam54ankdEd_$@7aYZXeuFlz;35'
    'n}#i<%_me%<^7m5)dy5=CHCZ4noWM@QTlQy^`Zt9WN_Lpn`z$u$bpjUmvUOQ!aJU)xIIb|T0MO3DiSTWWY02S{9js&2$T)MF=S25'
    'lb0{rzT1w9R_L7UE_s~(+S;VI-Tdu}X!i~$Jgd=SJd!YHQUi@x4S7>ct7{^M(T3|ozg1Dm?G-sT`1%#$bBpda&^gdo{@L~MBUG}f'
    'fqSRsU)^TsPDcJ9LtWO!&31C0MXs~9E1@|;!Hcd8gL~+(_b_g1jX05i_T}#G&WrsI;q2)nIEf1mWpou7z%s3-{eUC7)Q|&($vxBR'
    'MmR-*^$7&<Oee8sbcQL6AinJhJZ{9#%i|>|mA_FnQMmpNB_#r&k9oq;WqJDa0e2uC3ktyJ=m0U+TMnmRepABv;0pqwC<cdTa28+V'
    'j#=J|h~TD9usTlMwl{^$wuo4QI&4tbh0(5Zyo{ORU{7)#KG?SpO^2LAn!WB(n74(L%`)E`GR4l{F(Oz_XiG;G_3R9kzoE36ruT1o'
    'zd%Xcn=jg(GpE^XS3d4B_O-yzHbb_CFRFmDk9)Np>!vbip#>*qqo=&&nIgg*7s!G!`ky;{xp9dcHQ@x{b)>GO0>#oGtRA6nkg0sF'
    'B?vGf<;RrTE<`|4NcarsaBh%RAOe{<te28OY;p=9b8*h94gEgH(TY_0sPL3gp!eiJPw^;|rUrUgQVUL>lZ7@Qu4K?I=5}9l(~sWt'
    'q1tzfyk=2hkKxzUD+(7*g8S$N*<*M$HpdqgPs9*Lr5C`igATEH+_3K(Ccuc@rq>&a#F2Hpy$z(92W+WKddMP2rT0`Te?<k%>IMH}'
    '52e#5BioMYu{(M?+(gb|rXiOfh=eQ1D=`}grw1d0YWoP=*rb4xmway42C%P-DwF`isCuU+1s&aZ+Yn{c#7|QK-JAsgEj`9A)`l`c'
    '6x$J-EDD32ua)SK31Fa$XnnXHcwUdEO=5tcbL^<e#Y$1&$#Z~G^6OhMbV=g2qwZG*8Y|Ie3PGxW*&UwC&Cb`6MwWSH5zw%5Ijoug'
    'uyo=6y-m|sveDT-lXolr4K>Y?CG@+Pu5eWSlY^p<xgZPHzWoQ`Tb|{x4U0+QYZq_)32{>@@&p)m#D;E_Ho5;lBW^)X4*rluDduo4'
    '=@O**ds`2rm7NJ>dR?Wn+$6kupWV#X#2QF0fg)rEC23oI8=qSjR6wE)(&kpUmzFMbll_(RYKtcNXKbboJYpr|2}24Ccnvr&cK1C6'
    'wuAGT*slQ2=my}b#FvFa<a?&ZejQJ|kC2Vofm#qvnzY;F>lkIte5>ubRRM-y{9{u&c1)VKCbcO`U+ES}*zU3OQb{XsaS>9RKaJmO'
    'a=;mnfgTs_7|?uXA{tJmLnzq)vFz2r_zQk<j-$n(nb^@JPi5pO1%jkWSSO-$q^Q6A!8kS)d2ioW^zW+`68*$bT+)89de(G9xeSZ?'
    'CNk3~N|>izv9#o=cAt){`ncFLcJ{@Zw^`NCZu6#liSPru>T-H*5cLomiFefdNq)^2oVo=c7nM17H3mYiA~2bF3#G?96<GUFR+>1<'
    '?@-hd%Op*2+>VnXCxZU&h^*%gt`1;>%WS~Lm-u+7wU&vKc|F}B$!T(LAIy<MrVoKM9bD^C{;?C~ke#&vAV)ACPn8Oj`)8Cop3&23'
    '3~}@SWA;~R_DEzG>&BDVWPlT^l6WpsMjTc&WY_enNjEF==i{Nw+XrF&H<U`dtWYUAF!(a5SE)pC!vZwJ+39cjPG|z11Ajo+(jrZ^'
    'falA6E>_ZWJ3r|?uv4HCmH`%q4H>}Dm56Lp1>pAVXEGay+lnZkM@!$e=tIXg#}xUbXv(C7Ian%7txLdDgO!$a7lOtgQC>1Oho&wH'
    '<hKQ9iG!+94wQhGVe)%I;5UWC;NrVqhS5n2O%QPHXH`SMw}7>_3wu8^R>_bP1asx3uc|l-9d4y6E+PA^o^721@<+_$b<{`4!g_H;'
    '`xQAT8+i__=$APMdDe&kja&w9Rn$67L|nYqa_9lD6R#FWMMV}nwb2br*R!m((y6GnkH{P|LO-kO$YC?%^VaI&=-IH_9PqTScQm0Q'
    'N8}AE;195y0W<GV;L6gsgmW!J?1v;#!3|eKss{l^sAA7JipV}1I;rH;Yus;sltY*Q$A*J4)g_hoQ^W_8#dO8xdEbh8m1Dc^%doZK'
    'NG!TQiX{OC&L(q_%+q82|KS*3sU=Rkl6zD=jwW2RgD#)}1vd>JLb9Y`zi?m^{aqwW<VdqdhHpG&(Vx361h`Tr9uk#ZoZfB!M4!$D'
    's!!F862a}DN6lY=UX5Sa#_xoyVl)|uC_@mq9S99++!LnP{03oNJ1!jgL2?{Gx3Bm~85H~p4tRfj56tbc`;??9t*cM*g%uivG&Q@@'
    '$2YvQweu_1hX*X>uzOEo2E(WNUfPAQOW1*V&JF5e{1sGp^%h(OA)HzFU|$Rz8ERXCK##A!^GSLR_|;fQNCcdwfF}h_Ek<jmB!Cq9'
    'X4}obc9|nQrvdV?s^|i(Rd(o66cR-Z1XuUp_v+Ha8es0>)#!tCL3_VCU`K-r$29R_-o(({!%|kDrSOEJ>SdjBo^S=oNx213{G8zO'
    'WK;KO7{zV~5Vzw-@B4W@I=WA2-WEvB^gx-mr^!Vf)RuzvqhM<UPk<K7kcV<VmSb)NgkOhAb1@`2&N?A+mD}aMXM9k(6h_c2a<5&W'
    '2PXz`PlQ7T5RkaHD(T|9IW+AQR9beNUMIzPpuIPd8sf_Vd!2++n+Oh(a~3cYX!BF&7;V!aA9l~5wVSE>$MxjksR%e)DyA0)w|bqD'
    'TFJLpVkS7jo}oH@N&lUq&WUpvJd!<A5eP4?tPjcbhcL^7j7Sdi>weKXyH3<Q)wY2Im6`w2ZFPrq`|T0P+Oo2*k|_Ewb+@t=nauB>'
    'KLTy_DQN7iAqQIiHV!6AqLA&)uLSRH#PhXA*P2wlHgWHyVh?62<RfFGB@fZ$K4-1J@<p=1Dm&!qxmNgM(&lgR+I~4l&BCYuEIzqp'
    'X4E%V5N=|1g-07In55iDPAPJmMbm;{JO1M`#8QSdUH7Q|8?01AhqndMZ`0#KKq(WDv6FM^+jNq?1^8}ULNr~U35CMN_G_~_&<XMT'
    'qe+-$q9Dm>f6o9YV6Mv*L1Rxob=RQqNGrts5J4=<$6UQf3EY%Hm60J`R+p>PxY~!0&hcL?7UUs}SjQonte7est=M33a%u_&lXaVY'
    'GkCA)OfP?pIiWqI3$#N6!T6m%xNhNc@DZrTR#?l2(SGroWw6dE{aXDX(xj+pCuOrvZkrn|Z(z;WJp0rJ?UXe@y+#(k7(w!d-(lfa'
    '2H^|?P591Ph`QM2hja0Z9tmvw=NyT$PRa0jt_lwXpZ^l9k^nixyE1-JI#Za$ZBjfklv#6PV<(rh7`s!0B6i$NK|Zg#m-tPiNAN*a'
    'M7)s38K(8?BN8AXK0V|Eq@;%;lS?(=j1jT=Tg$Z1)8Mu^g@9S$f^DHl43bZ0a_@$jJe}Zij5@S<yANcKd<mwbA)5x<LMyDs{(1>k'
    'VO9QTTkb+ba)^~r;K*`Og%R9%qR-LuKFgJ{@D?iZc+AuV!ToqbEoqYpqW#5v%VPmCqibf^Ktj;;8>v+NS4Cc<&7hQ|xEH5hU<tnL'
    '#XD)MSJD1{GCZixuu#0*a<z3V9A{dpJSSc!jB5THSAJb9w4uEwLi=Nuq{3Ti{Qp(m9QI*2xs1H0p5|2&RSA$J?k~@MBma!hucxE>'
    'aT~yMRz~SucdqHfUl1{{Vug8|Z`oS4g{cxT6>w~S#F>=*x#in5?SfuNBSMu27byx$yYd<aLp_wjpM0!sQr3VmtaWzs41{Hahlfm&'
    'Lt1_Km}@zfWH?}W+awHD3(spT{1<5XQ|G4^ENy|We%Zmw>|-*gFJC{BX6fZq#o)86l&G+JCX&yJ^|-zEiOuB8YQQ)HYcXNGGKtOc'
    'PdjM@=S+;;B>%hTGi1vrDI1loCRT4$92YiOzOqX`AOi$h@(GEc5m<*o7G=a5pzqNYmk4D5baIhyXZ)ij22}8m%nTJbLkrjOaLk{x'
    'MkdBG29q8Qc{2|j^}tujAgQRiwL>tiG3J28DRa=N{Q{e(9F0PTNVYmduOX(dDTgq9k%O9m37^&TJT`6gTf0TB{`iE6ot8`{sZRVr'
    '*G260R4s8b4Me-c4*+zscOj;)FT-R0(=tmKG;SlBRpT+)el1T<!+07fo|c3uQA*=D{8=``+@W9Mc)Yw`{veq*I_;D`^WWTGly>r-'
    'hm|mLj#jx8*jie7OfsF{5Wv6zo(?EDRrC-Pe;^u)Dv`%AvMWWlJ1h1S(yEK2ion6+igHnaN0CTvZ5BZ9tB%MBWDV)&=cJk&U2zb6'
    'UO;pqkc+Y*WG_+<cu<lbH2|($2Oe-v+&FjuldCnz*jP4a=@`cx(BZ?o{zqrpXAX;Gs9|mhE&cRmljg%x>@sK=RyA|O@Rfo(s2v~f'
    'T;U#sWHYlB_}}6GKqQZdw?maz)N;I|YV_1SshUY(W13}_oABT+yi6j6Bm6D>XU11d!duz_Izs~xbY<J-$&um6FxfHirI|hPZkDX<'
    '?fqZM21NUOh}-V!Bw_ZerTyhV=g3?(%;Y2h;>KY2UQTg{O!l!!^`!mL_v9eBCBR2K45$RM1#b)2OhT~V-1TZCdiRO;#SGKuk`jUP'
    '1^2n?GWK^`r3d%*>Vy1C(mnk~^J)!hroHjX+AKg+hYDZ5{41win-COh8l?4LWCg2rWj{QrLSNKLtWN&&iU5xEFYwM-k*g!IlZ$Ah'
    '29Pn>FFAI9Iz>V>E0F+nc6t};^O@U7`8!V_)*LonoW%#NCj@jeHooD6EW!9nU6aBq=G?M-e>Nf&M|7Ntb1~ZN;%x|6b$hl4ye5?Z'
    'O!?c5_v0pu&Fdqn{#TL6k8$o<vJ@~Mb?#R?Zu-KWyMXF&76z1NrUy<KgB;rOiKoe%M4!!vO!UhZao1;{1%$l$Jd>x<Z_^MyR}B+n'
    'LNI%Oy4(rQ68@8#&m6H>diXLUppT$xJR>{_JaZYwI@E!ALeh4-mINaYe4kr}o7W|%S7EGjV?*~aZsB7T;3v!9#gop0!ewjbQtcR}'
    'Qm|qL7Lly0usLpTwu@*Bqhjm~+gWg;cI9IRn8pWmo6OqS8fMid$U(k&lZC7VYIUekul|5t!zn+a^mS3w-F8}Vg=?-FxGv?5xb+nN'
    '9P#RVj(G!+klih?Eez>&CtGc0f1FjGTAjBy*FAA0Vgc8|>ZU>&h6B7<!u3LpN@;*YrbsMlxdGdM^z82F`RZ0VdP0(oFoh%ScoCs0'
    'n1M%m_2W(TjC42Hf;{nhJE3-?f;gjDLGYt*^gk+tWw%WNh#3zaSk7%kT@K~po>A+i@vN4D7<+kap8k0Z?bvW2P6z(wfDyO}s4~<V'
    '%kMHI#v_mLMb#gVEFBu9t%JxGB4s{*;3ap9$hSq??LE3$!cmp{ox<;s?4yO%O?`R<eT0~`fBjO-J{^M}^NL}R;=b3}X9GE;zk>=H'
    '^!cgdKrgjNGc=#0??zA&j|Wn_@ZgI0^!8cn_EEF+JQWpZIHM(r+3i&kB{Eu;$a`8l<K2Pz!@s)>0mILPC^@r*unXF()i6umyStpn'
    't#CW)Iq1yWh8d|0=)PWa;U^cVWeKEANfqa~KBC#rp6b-_AYcw5`nnetnah}y&HUtI6aeFdi(C5gET~lM-G>N<Qz(?+htC7851&LU'
    '2UYYbafOW$fGXoQQB?Gb()}z5fpgR*5>jwn4|9ZxFwy?qPOMv;B*?4jv4Hb|CDK|V?^`Je2r5$YAvp0C`v<(05v?U56Ar>U_XI(5'
    'S`Z+aY<R8bAi;ELk$yst0RlNU%{Rv&A$<^#d*1Z51yEChNMvVq<$B!E#i5^F?la*->VQ4(&j)e~R7$RjTkrDYrPJSVOsID&Uw2Zu'
    '<31at?Zb>7Du(1S1PBNIGzr?CVzY33)oyY#eo{0>i1t!v9ay9gmDd;Y0D9jU|E(S^65x~F3`@pnwM8P#*RX;fmYP84RDtc3N-~b6'
    'Q_IP-2j7G17PPfcTwLFHH%Q)KxwPB#kAMcY_uGYRilTZ^P3<Qp1Z(VFAwIFdrL;}^Jqo!5tpgPNmpDZ;;a5e6@^8D<WxW`3?6L$+'
    'hRg~;sG)0LFY<MD<siZNt+&ORUnlx`gJG*J1iu&kHlKD1hYV|ylFTwl5(3Tzbe(;mPU27!g<lh&`B;eA({I+%2x+O*p&#30AIwI}'
    'CzEEF?`{@4ogdVZc&3iJ;eh=<RsG^qrLoFWAeZN6rRZ|MW;295(|W-VfKR^J(^!o{*D<P^>xJGdWjmj*QIYKdXXoq1chI)Mthk!N'
    'C$V<k^3NqAIHBI)iN#gr8xQcsRd(hU#9HAIt==I)M%1G*V=`VcIjOewRN}X5$HjMJ99|W|1II|hOguyge(gf}ESo8D;uPYp_$^WK'
    'hoOxGtT}r$_aF2odJft;<DGWgqU2XYkv|jcyk#R0%BOZ^gN#PdWc60KKKgd9sZv0A1>O6Gb({wLmJ^x<k`O3g3qu#(&5KA<Ht(gi'
    '>O@IH&de^IJ~U1gj2%VanvcIfi3jZQsy99|HDd_+|Hh4~VrgPfa!{b@MQWyH8=hOEmw?6%=h{EFvE9Ety}wYma%RkOERqU=bswRv'
    'yNOeRAG^eG3u$mYpU`XZmE?l937bS_zO&d4FGs}WA<a%an>J7~xD=iHXOGhJcFQu#H>cDSB?8Q4hSH|mpiE)G3YGxk^axpDP_9RW'
    'jJ)g!%?a5XoVva=(m8qlziKrZTc(%A_hg<1aF7V*eWNKkZq;m}pSO>T$F%a?Yui{!uf3eM2qdUVLw9r<V42Gdmucl@<JSFS9ogGG'
    'fTNY2j&TDwF>tu4G5h-kbu^Znkt}xnB=t{zbn$Wlsfy&)khB3%HTU<Ks}^0E2~|$W7$3{9IQeMS`HfeB41a6E@|43<fWDmnOrgtw'
    'yh3T*X_P3pRxPm6HPmTo&VF{=nKiEHiCpttfFZosbLND{TwV8zWa3>Ai7VsdjG(9;476mI->#EfFkpWCqkMAZ^^-Ck%5~6lbv2W<'
    'M-TQ(VQNH)mM8-Eb#>g3n=@r-1ezKb)oF(#`Z@r4GTFsXLmLr$#w+jRf<=lX?)+GYqObjHHMOck3J{)E>GHVM2>~Uk%Mu?{0l3Yk'
    '5C3~7ba<4lM2HUu+YXeX6*UQ5JdZV_hjFAd|ABcTc<M{=nkY!uBp*o5NBXrQ<FIY6W$#QYymd9=ub~Kj6w-Jw8$M~^K!t;)rFH1W'
    'M4l{A)_64Kr_ftIGbDOAM?DQ~p}TYpDpA~QuVaJNCvJX1xP`Uw2HpM1zJQUg44u9BjghCIGmVs2wGl?8*U|MVwUjRYvV>g?n<<QA'
    'zcg$uGlhE*XGI&Y*_%grtCsL)?-8%oB^pX1lYTg%Ms2h|(ym0=-abapKWeItfEV<&LOk(aKUlfbg@Qey<7n}P<tJm$*|hXn-}bg@'
    '7KG*2D)AtO9ZXuFV>#na*w|0|LMK9P09S=2WkLerKouryj>RJ@I=wYPiJ*yYvb$y5O<fv7WaO{$r3mR<l&Zlp>Pfr@;>gErTmw&8'
    'z^RBnOwzzLSRNsm;vjz&Y9lwNNk9a?j(d_gqI5}QBNWpCP1W@3+_xaG_ubLtMW+fE=|-wk5dry#Jpfnc{I)qs^T$_swRN@)mkq32'
    'IK9>5DXXTH-xVB_zXdFW@k7}PxiS7GSgjz{KQ{&Za$M!YjoNfj%y3eR;FB#`x7#AUJGpmj!gU*A9}?#|HGOK?Yp72rjY<Vfm4&0_'
    'tpRz<K-;N5$(XdAhsjxMFN>s^jyQ3rK)^^$3yq+Qs=ZW>0l=g>xn8kGTlJ2qpbb}&M?2ktW#!iG_slxX{-{geX0dKLKW0M$hk_b7'
    '|Gt{X9}LqAL>&)zg87CRiCpA;&yeyMT~l*~P;Cm~vN)|JHHMbAu(n=Y2RD|&3TTm(mcmqg4c`(`;+b|xUet0oSRxdO7PYc)z>&ji'
    '9pCAcuM^qx+4Rj~z+MqC@8OptSwN&>B_w_%545hi?GMVCwju-eB@;rJO;^61ZyQXu<j72uq$zV`?=u)mkL~0ps%m`DCSdP#m6H-B'
    'a`-A1$Vou-cG#?cg&tQYaVAAY%N3ZChzh%qu}AR9p<zPi90TqWQVLR9-unZ7^Irfq_*Rt#J=g*GGV~sp$P(=d|Ep;J5b>#}yz*_O'
    'HRFmoICNr4;UUpEFYLgp%-qQol4)ERusZMkem@HHdpE6B^cw8HAH%sC?B}J)U%;J*10dVnp8DJAtwggiz|>9AiRn%pHka;q(b)7F'
    'O+TFcEuh!kHB1)rdu<gmbI`@;Fuc}+k*5U^Kfc^1<d2!X+^KZ;6Da~8g|*kG(S%?5uDr&#MdmJP{#ATgKp6bTs$U*!n5ierQa$*J'
    'Fi7RZd(cg%+gWa@sv#}Lcy-pn`y)Flz-eNTm{A%sej`K4yulE%WQDUF;>$CYd|EwT-T%|A!A39?|N1Gt<u5}0;y~Zqyo~)YSB^ZJ'
    '_z2ywymnB)l$Gz=Yww)#7wgnsoYxQGSEnJHuiF{-r1uoRQ*z2a26{nkc3-|7>GMV2%xb1$D{zm9wR{-h5^pA9DV;0*+}U|56ar#X'
    'VFVKRR*IgCG{UFyICg@=XUkz$ig0UZ6V+k;p#Xd~rPhDYo|M^<{#(1YvQQ$)!FX~=kM=m`d=8;Q88sKPtarkfNEF&@T}to%M5f5t'
    '<J<Df*^Skdh$-2ZsWJ?S$YQVa2~sF_Ei)KTv|k)I<hLvs(JYEzC`0CW>IrsW-4(c_K~*X~(EG7WGD>Q^ZNH+^Q??Me&-5`mbNdKp'
    'b|d}_IW1(gmoedWqM<T4IU2p{k<O229&KRv;DDzmpmGUvd!m`kcst!AXhd~kp&M1=!81D$-07|(B|WRjOf~CA@lFK?nU&A69z9#V'
    '^eV>ALva=Q<=D{e@=0=LyQ0P7azpzH<X9~-SZcGKa>ZWji&!Q2%WXOCf=Qg_PoSG{Q&yD~mqjp2{(9<pK*st?Sj)M)qN#5T#+);('
    'A#yF*xXn#g?<tfE$=lp%hFz#Js7sK0{z!r>&&XJ7u`jduKXE@-27N2UjI<w-VpXeqctS~Rz*`{>!wg0#G-}~<cDW^K0j(U^nXFy?'
    '>%bP!X?1i1Cnt0xHDgTD1^@U^5lGsQbWK*F-t4?1)0#Rg6uvz-@mfPYJt<>Sdd;1`dhXN4<E>7Vh!PTg3EW|p8NuH{^%I+I*<KbK'
    'NyqutA{a^-hPUi^OXz5GXfHq^JP5uWBlmY&C<+`T@cJonwOAZ%H9lU7&#$jtD7hooCWsAI*KAqod4yYbyf3W@R4J6xRhfv1CECkv'
    '_2RwHD~$uFY(O8p;}dYy)2_r7mx3x0ldq$PXtFq*9A);jG@PD_=x{t})RMt8EE-J&&O4#Qsq)KPwh@I!E%}nqLtZ^}E&Zxe+`Ca&'
    'De)on=o+%I?Z{I~(NwVHuH6^;&FvQ5I7wE*Bp!V4I6~aG0wYcvaU5b}5ih)DpN|s=dSdKmp%$$oM!9$#?Cu2f<Mc$&%s?qn@IOm)'
    'S=+rLj1uciBqxw=t}Jx77a!1H%a{sA*jB}@MX|Bk<XIRXd+F)?Sg-BT(HFYZ=rNKr4-%dnyWDRJsG=IY$O>Cnn{s<AW#6LxKXVK#'
    'Nvl4<M*k2TIkzKh#MEJq`JM)t|4ZN%i^}mgUdSw^ftyxv8~)N5oP?TXC8)|vi;kd6QI9>?*vIS$67mkrUo;HD!un;(D-t$1E`V5@'
    'TuBKPIs|bF%7Ra1pIQxsZR%h(LXE7uJm)mY*V3HA?_e>W33;YJ>B^sJZZ4g}>lfMW?+(|_UV%)=W<XeArMhq_uoR`)(Z{d*BKSSe'
    'C<G-NjVh}J+o+u5rwoj%c5y5)p&S+gbLjg1<FEusyyLk^RC!Y6IyI}9K<xw=v**mUUD6$FcD(Qf<feIP`BOX!k#NF$rYIq|Yc{l|'
    'c`rDFn!9nn>+$EdgA&7qYu~;FwZnG`Bb&(;@u1*1GuS@ZyO}B@_?5J}!crW{dpzW$%t70bMg`J6TRoS}+X!5~PhyiD9=Uo9Ki$2m'
    'tL9@JvyqJ5dL7B&?dioIDNHL1GjKM}4Vo1_{w=i`2OMBJvX33dHS%uPCiSma*Z&1K{+2aZGmKyz`R*(1Q|X^PKJNd-Qpj}*Mm}B3'
    'r=K_*(s|hRmyUT_JzpJAfI6aVcKj<&vH4FueWfi{pT6KRz&B4UQT%$<ktQ_SJnh>z!8h~KHK02Jt^e`@0h`}{bX(i(1lk|^fm&~R'
    '69^V=ElG(SQjTd(>`tjn!`R<=hN@d#U8ch}!7ua`|K%c<rl?HgSmQI>@YG*o`{DBcJ!bnLLhFy-D(3&`PKdW>cieQpF`Abfmbisj'
    '7j9UyO4zOO4gCTn?%jI#5tmE;uI2`%b;T8$2TS3u563IbV4Aq2otS=sguSx_uRE^rAL#J3u?bjgQ!VZlCXTcIU0!V&WiNuC((4!8'
    'MGGWlb@yv8Stb6eDMg)>XB~`*fjf$NK}inM%zqKKJBkqVJ;_Okj)t|x<<S8RfHd(qOX3cOntQE;31U!-2aVl1Q>W9T)vd!i20XsG'
    'oWfM_L;0JhP4|7|fV4&nDBLQsZQdb;t->dLpX(A<<kMH&JsIha#+V@)u=jQO=#dxVAGx(rtWmOTzz?`iTl04!-Y7G8HLDA*b8p$Q'
    'P-DLGu^_h`y`82d)=<ag<z^6}D4Q?x#bBS{S16y&cGyUVbk5(T_;NS*U~NBl__EvKK~&n?;3Xqx!)EKp6R{c${b)M)OsA1Rlt$@e'
    'oU+CPc;Q4fHjicg5Ej@G1?M+v=?m!{Red{b>&gLopR%}sF%c+a{25O+0}+BYbRxpFUvj@)9*x;Cy^#eIFGJS4K9p^^oEPn`v|1x7'
    'y1T#UQjkNQ4YH{!j)E!wAB9!MSd$u8g*#NJK_{&ZP2(D_NRSN?^c1Hx3idOgv6W)?VtapY2<kR+xX9py$H=h(OU3Wxa+;4q*Ik`^'
    '?o-(vw|D2OHZcO$*au1kdn(99cSs#d+95tRvPxV3JkQHbEHFs4pEiFl8E`8M#dKEogi$7)z^l8+v^=zgra|nwzhokWq&;EV&^guV'
    '11h#$JsQYkJ`5{kpk%dcY_4!B(B;yK-~W!o)jZkKXmdx#jM3jbgALpOoRHeHwWAm;PYn{wWKiA9qL*mQ*AN0^T-+$Za?K{gJ!)<5'
    '2(_>c*KJc0%_c(@*CE***D3BuG0&N+p4&<rID%nNxb>AK!<u2gVRD%VvxaB;QB0zF_=XoKwp93yU0>7{DiLaPGKfd+Wko?<88`Rf'
    'if%STTS=WUx|&FN)vlWz?5Pe`AH>6Su*#w2rxKX{sHu6-`m9#7f!en!hTp=+Z<wXj=p4JvKIMI>)+G0tU(0(-*5O_PbHChNhz!Dh'
    'pO_gFCEE}oX2Fs3wahxy*^O-R2~UxB!v9y{-bW(^M{S7h`DD{(vFZg5zKU`^(Pqf;RK50DIU0e@PB&_eMpA&aQhw35;_YEj*&7;m'
    '5Fky_%(HVyd1o9nl@=J&B|5GIfYOBMs@A_X{#L&80-aTl%*exorI(Z>%4_=M-cmt%k)9HQ@bYc^_5V$NUK=x8CAzv{jwId)ft!N~'
    'O;o*keM%T^U+KewlbF2I8irG|t4<WzDCQ(M!#GXcN<Q9|0P<X_33-LT67`?4C&HRHC;N`oxz(j~>hm{+UL%g9q#^Cb{l8~n20$C0'
    '2uRoyi~ZoSBcqQlW?DMU&ar_*1PE3IhR8)xNlPYsGpB8!#p_85>zU7*T1!k{0RgHY$>!6k$*r@woEDDOVL~BnN?wdfTCVlY$PA>U'
    'h*@A;J_VrfE9+L|y(7DI%d#a8_zu6wpRt$>o{A=ynoR}1QrT&`=9DC~$P8t9{qEVYsD}R*EC(+3!HOd;#D&bZ*C#;MRQ!}Q%4*}&'
    'l_T6R)+|8!LT=W8LP%5OcR3=nlSHotlH(KircN~gjsYXf(e@+$E+EFP%mTjPjh|`{sL9|CT`<JWpEPF#)3Q4|@n&POfh8_?;m^8f'
    'swcPz_!8S30%d$`$^&vE8;`#QInGo<6W-8QGnc{JHlDU#0$hg$_f12-jUS|Vp;(I1<Q7_d&xC@sOj(_p<a+2hk(qJ92`j;DKYn^`'
    '%aeOMs{w9f@Ay7AX#b=+Sv`8{b@<{R(~v4boz-_$d3JBvzsl9lKng3H_FoNb>lWO{c%87`ryb)^S{<=m0_nn4zrYPYHd3Z_(S6$s'
    'h(s2IRn`={+jaN^Gcw^ZE-4{=oCk-V_<)*ohn2c`nB8Cd$klBLpq1tgrxe$!sAVYJ^2K@geD6X5!b!|KG^lJ*JF%af)O)M8xfANu'
    'LB)X5kro&7s;10&sDus8%595XB^lEeKQBf2bUCu3m=8mE9w=5D;4(RtAdBiu?BMzJ#v)zK$f0%zrctuWW?^cAm6JUvWoUQUc-8^('
    'G&r)-Mw5qtVX1<mfJgC!b+S7Sx2bbknunj)Ta`5_$(=R)KR7+_1i^~k5-^y4K<Ebh45e;a<EyQ2&_35YyycY{M9>4%BnJCP{;f_h'
    'lfS_g*I$lFQGnS2l+V-IvEU^JuD=3A?O{QX0Fy|y8D=J6_nIpVzBsa$PG;wHIRu*5z)W(xCbO1!2>w?L>Px<!Uy8h30yuYiwvs>x'
    'Sn(pBEFd@p-)1t01yQwlYFzcMww~aT--uoH?*8-*#^?yrfdoW>BiNAOoc%6k4gCxl#<n+9yu2|HrG03u{B9>H(fsq+;S@U)5e*fx'
    '<YB>OJ$I;RF>X1{3EW)~-;N+|5C8-fo7QsoY}Os9R0Vj%x4Lqd>LzVZZh5D0BIj++IfUc0&?Iq1EY^vwyce3CENAfVJg8{3z!CA`'
    '#GsHwNIt_31M`LdHnrXgK;E7(wwUAbzt7V4f)53F_G&bimKOGI$kI<ii#U7xPG7DHm``onF@jgPzg}55EI)U+Q-nq;qB1zqa;P}*'
    ';uAU;TK&+$KXGg8keywoX3W#`z8tr=H|oAiy$XymqO^MkXd)(inR=D}NmKNrz7-5#V2h^=S&8z*zzp@z96ARu#%Ob#wEwsYP^5nJ'
    'bg2$qdl;`Vm#}9ejzgmT`BP#@5FJa!-DuQGN);V-zzrBgRl}YLNxVbx14`WKpKQ@SPUA>Sp~w}EV<Q^bkZ+^#O{8k3mnE~XZkKTZ'
    'I=3*G&EUZzSba@4D@;3L%R>#qB(_Ide9kPj^sHR`-9iF+=VIy)NZ$!=qRGV8Z6$~TNRl?@p2mmRqgetp_Je)>Q9iOgq=(Ug3fE)D'
    'bbL8@nTh1^JpP&4L%W1Wrt*<UJ&6*b6Q`z(%n<#CHF9pZKW0~Q-evl_jqZVYu#lyi^U{%Tzs;jS=t?>NjukeHEl@vQ($j?1^;JGI'
    '+q}}PSyuHl_LUGYjY6DHVQOV6<%^w~oz`~aG3}IAU%Ui;8jDeLRMn@XRI%QNTYpA&6_36O(RkzPg3fnot$ozLp}o@q9b*mhAl1!;'
    'Fv^_ivhe6UPH(S4&veijCnZpu5~Wgw^@XM?a_|rq-8uGk%vFIvU|gE!ugOCBL<Pp#mN6*h=8!x0yRf(UsfO3RZoH^X@jBamG@M5j'
    'NxhIw^Bh|U{+-)c;0gz>^&|7lX_D_aO#)OmL0D?A#bpK?vlkR0a?tq(H+FO4EfP85;1;tpc&Ix~|0Vf%7hNqG&9PCk;yj-Oy3<`M'
    'D@SCcky)yhMs6u?0GU4Cf}1(WM6+<hVN1|E*+t>ITrtkfrSLIL&qS?{>wPf5d<m8*M_}25n$5!~48%P%u0_AtP3`I6J1}?l#s#(?'
    'KQK5+%+adJO!9o+nlVmgHoJlhMo?)}m)9YrY$oh&oY87>1M#n{48m>ac<9JGHs{G}x&&1;EhN;xYxjoz;>Apn5d>tnQgqW(8jnId'
    '5s6CLbGyaocAZ|tZQg-I!kUw9ybV@A9U)qXQMLIVEPH8F+~-1<f`Y`pU%=n(d}taOUv2lt83LYEHKmknKZQG@4l(w!fI1MxSOk_6'
    '$ClQx(M!<tc=XS2GSNYcw{yCt1?W<|)%s9Kk>2kJ8+nvT(f_bv1^SxzI*!%Q!H<4Xos111z27f|B!J6Sf4qNMbOT`Sk)x6=H2-MD'
    'J>iwyApO%uFUg<=dl_QIAEB|&$8<ughfvsu1y)*^i{AvY3FBH<2-JFDIpSeQNS|J9(DAfV_7A&-yYDn<5@73o8I>4eBV7d@bH8}m'
    '9M^buJEzI*>a3M+?R-|4m@wu^R*LZY_88b^c16Kk5$8T^E$0+hV}1(z1YMYQdo<@MuDX!vul6KxvX#XQ8g#Djj|kkkLy8R*s}o&9'
    'S)k)gcE!T*sG1qVf9%~o&OAA|0!ic8z8=q~bnC!nDaRCHvg6zPe_8P3$(F`OXT?@d$kS@Np`bTq!Q6tjj+=U>JLuHLzSEz7sSRT5'
    'UHf`R(1{oC{g!#K=(+!DLDYTiwMRxisf<@l)v|&6y{t2&4)C@l6Ib=;wQ<+QB@v@@O`U;-F}$)oGk9gmC5+j6YAqk!Kflz&=#ZyX'
    '?s=?_caKlAjiS@bOOSrx0&#@5-TZ3>xv&Cy-I}XYT0j?3xgZlR2Womq)uT^;D^f>-s#42cWp25&N^D$=tIQVyl}_ZIpyf#sVxS4d'
    'KZ=o7!|OPyhVbX_xGZGqJ9ZRF&LZ@hkkpv(7(W1d)n?IF?$^52MqGp1V)3tRfK)9eR-*AkUoNK7L;WA;oX%Z<nl0m@dC0h-b^y{*'
    'KR0rOu^ZQyRE66g5xvRD8<JrY&i|)B{<?4Xgx}-Iz!!4+oa&P}@%n-*V=|=n91HS_j016Mu)tB@>2%u41r1T|KwWZXLGk<&sDPdl'
    'PPX{{q5gBKy5(P|!z4e3bKTR0hDjk70NZ<zcsf0m9=!0^^SL~2efLMaMIqk%LND69VXF^zbx1=&Tv4Gq<Z6+AU@2F$`@Oi$T<Q^H'
    'H=eV=t&}MW+OZEg^+IIbT0Tae7(wS=u|=}i+HE_iLNmNLb57&OI}e@;yEt6Ew&$74a6)_K$)oR^(1DAW>mCmr$FDh~pE_f%jIMi}'
    'L}TU+`Z(2A3K!H_8NjZ$_aG>b!sTIDYqX<kfoPCXWqZ4uq_nseTil-pL&MJ_(;uT<uWAM<V!5l6V5%R_SGimIUaFKBm3n*{*=OJ<'
    'R=nFdd<!X^W=J7eX~*LP%b5^hOnb}ZPW)(~+;e5@6k2f|ueeh48vL_<1~AU)t;izH5<0EWHzhZNUm8Eu=GPCRr$e_BtM~2{$g(Rz'
    'z#mKIHM85*<HuSP4<*&W@eagx)lid1ZNKkWT(MKsd?kK+r#RGIENN9KoK&>u`|X5}l|0=c`$z#T#M4$Eb9aO_fpkVGHRwe{q?!Dc'
    ';-q79zP4+!V`{0S5<;NZ3&vIb{KoebQKn@YmTe^mD9?mz_F9B8Kfomyw!XOWUBkgPp>4{bGg9O}q&yWqx5DBy@Gql~W1`6h0%rXt'
    '*xLt{{Y;2yo9wpKW)`f`yP@Biw7>)U7W~}QuCoIQ{h-kk-h9i$Um47Wu2c(pXezLHIxynB`{!T&3Xv@zkFtAvhXXE^F`O8Yc(ER8'
    'Bb?1<p(}V?*baFqB1e2&I}|);JjzgP8$UFe63zR*rO)fHGcdpwP@Zp!GmH7u2O*0c5A4+Q!O@Tv7k{`A(>y5F|B!U=>ezCFCaaf@'
    'B$&5#Oir72jxq0=hieAu*8AvN<dfy<DGcyf#R0uwTuB4=QLkSNgZ*T;1A*I|Ima|uFzlq*Yh>s$ijb4yUFp2;QJplpOOB(%SG*J$'
    'wJu1pR2cmh*jSk$uMnN5LHVcE0j|bbCJ)ZZG<9OzNcg!ny;J;|9Ho)A26)n$$S^?__i}+=9!Zy&?lB>uFVmw4$p!8zgo+)@dkhze'
    'V&7EcIq=Dv0M)7mlNQ2<AOv3z=|!;#la|sMva72NqBpdF=#XGBxsz;LKxz~|<?n4EsSl}wW5sDRQ1QaPMgjXegJcDv;VL<i=WdX('
    'M{%xm4u&O?(v}Tt-5fcg`=SQnb81w36DYX+%x3w6H&(FXvyXl?ewJ^_1(EeW@^I0m(Xd4(1AzEjPLc+6m(CKoRn=_r8Rnmlo(<+S'
    '9EWO-K1W)8@edmOS0<Z$y3^pD*bV~{pmxF(VI2=577d|X!Yua-7B|Fz+H$;x*9EFCdi$!n!%0_3$-0p;Km4=beRM#=Y2Wzk#-BEL'
    'cM8{t`_@)w1D)J2N40E26B$p{xHt+qCCrrkeec$@mYqRwnKHpWFo|Lq+KH)9CBo1S{y`bzK^1QE;>K3stb(LcXa#F((wm)|vgcpf'
    '=+$qdF;Mj*-!diM_coEaYWfSwU*87pMpb)dNR}(p;oJRy1O*{V7j9WTJ_dWPBb^)&nWl}x)h<X-+7}0}X9pVzOCgS_|BP84(lgBg'
    '{DQu>6FPZwKtrAT<q~hnm84J6h;4nhJYr?IsRCA$y#wO>!XklKrF6!*zBwwhLwAdovyQrVz*hK9c%dbJyUx$k_N5g4(9L{Zsu*ME'
    '6*TUuC^7v!wF6m8C$HL>JZa>gsOb$bb-QQ*p`i9`XaucLvY4EE9my&o4jhj+cxZ_X>h@)f%fDSxuYKTm)Y(%IM&)MY%hgo#sE6;4'
    'W`dy6d@~&R<ag?bG7B6oq|?`)xpSwhh8;Q2@gl5X$P7;1UNQylTk_C^tOcMENXKUpP~k=Vx(InRQi>n46oh%eI`l37TH+CRNPY&`'
    '(H&v{cRJDQ<k0cu9kJ?Ovni)Zb!Qi^SNy{%^QNFk{le);cA)W%T6wJ$3bK`DiEbR9-UN^NJU(Ta@AKJt6~@g*lwf>7ABq#e%t8%s'
    '<mk32O$ws)N~rX_*zRVK<n6nG>L_44-N*6cX#x4EHrE)eySOl+8$uX&Nc@D1>xwEYMAud#lIejH3FQVTgpi8^9&&RDiQ1=yFw6P7'
    'c*{zBGv6qpT=3YT^LvAR@MGqPb7@sLGuHPZIS-*g|ID{+C5ma~1|bhX#~G;Hb)zFiH{(!{?{G`T;g$}-jTR96muNNfKl)C5H_|Gl'
    'oVyA?Kb!{=B-td9J(S<c>H7|Dyd`)j1kp(^*=?;3?bZUCd3PelKWsjNJDU_wb0_>3@oo$;ag{5$6uYds?^Kj)^^v`>-BqtAMr1PT'
    'B@9dy9rM1F755a7fk~tXHPFzlSE4B*m8@NW!I?iSi($2kWuUl4Wz^1Ugtuk#l6|6XrM6BK$|ua&0zkHG(#!X)Ug+3v`@9JH8wDWB'
    '3Ov}EwAAiN93&KOx|W_f>NHAftXTDiAeF{#7fwN6!I5s(-eRO6$z7>CPbq%D&2~>(Wy`1;GOu=6;Z*8iMwPyv@k0K+eeF__EJmFB'
    'Ih=`#t5|*CVJKWeycJhr9iv{x;tF;~gklxAFuiUZwhx!#x=Dbv8)g=qXdcgpl>N}Of`=UjLR_vdfm>t~SNv(Z<++FGDHaPvKu|Xe'
    'rnLuL<)+pLj!?N#X%tBjh7r7vN}^2?X7lp73?T)no9!Gl2Ak;ODHq}@;o7ymfLB5$5O%0Y7Yg*lyI!j+wdjN?i=l#K;Ymcfbd#hY'
    'z>>BT!TTxW$Jcgt&d(+h#<o;15^M`BUYntem;=&6AAa2%wfK>MP)N(EO$oOwbv&h){i*HA_c&9+Lm6oPjoJ-dldiAhI)#%FY2NTH'
    'o#E%h@Mhqx>477)J16*tUD`c{8+B3$4aGSwFWRjWL=<nUwf;y0)kxB^>sjS7!G?kEa3ylZ;0#eUrB`(UWe2yIgH(KMWW`u>4MnGv'
    '!Mu}m02LCgUWIEv>*7yZJmMq7%h5bKIdyh{0fyNX*2l4SpHo_2zVzR^cZEUce;ziMFDk;9(*;X_Z=nYTG;lUR8pD*y?zuH8GyEjf'
    'jeYf{Lzp86Up9}?TGRh#F*#edyhE8w=o04orSzH7x2s^6Sj0f|6a>;rH-ml=F=ZJRs_m`HHOzA|08yDJK%AvYs>;w&#09}d`QpGc'
    '<;Ao>wbIKaFM%lBuZ1Aj*Cz}KFB!m6dr#4MBVsCnP61SU(+yJeKtgi2#?@iKJ8MCrb9;knT+^4Xpe+DbP<d|^yf|`*dTv_-K>dmU'
    'jG%`lVoBAzJwDIJSU3-b43X1p&%7t$YLW1+_HJ#ztUW9^fCogmptFV4&B$jFqUrJ8CFJ%J7+u5o3CP|2XyQ>dN7ZrnmKa3!?0S!1'
    '*+wZ>lX>vqH7p>!`aC+Wssp*gE;ycC0@zji>)BYsPpfA>B{QAj1){76J$L^rH?fKXZ;LAEO8d_rxxxo}h4kISory9HV-g&brjM!4'
    'oc-3T?JN7w<zP3y^rDpwg&<h0rg^SKeFo>39<3-c8e(lv0+4rEU8wq1BEdo-7{hW^8WGFNV_Izxn?eJi1r-yat_wZ9a7~BlfICIZ'
    'VfhHj?#ho!5wHyJlDv6np~l2THj&bizl<+>NDr+1)di@DNK{&cXV4}miP<;BYmFv7zV#t9Njwg&99_e!eNk~0Hu7RHw`KJ69A~lp'
    '<E4d8CS8aBzU@MDgcg}!n%PDJS0sgYFY4}~3A4g2hOK#A41Y5Mg^h-d;VyGx5hPrQ0(Rwy$NCXP&bHN#qe(z%(z@Nmab$dDxbvL2'
    '1o{W7)U~S_a}X1DvkOVQASoA9bZLaA2Q<?YJpQlL7FPdWbRP&B*)1qvgMv+$W`E3%6j_a>19u@{I_p=)t2^y&F=NrU^o~tJv^EUw'
    'q*j6zl*rZvL7Ugh={1{ZY!&U3yF&)1&wz~9G_YLUAQzT9mqNUL#ZlaavVyuVJ2=p0fzmXrPUR@d(=l^CZt1{%MxAL1)68|V`fU}Y'
    '&^DJaLl9A^Q>fQ;DOiy{IJ(nsEYPHJb4#i8L)w$M=4>9^e$|h~d)v#|wPhX6LxcxMLRwL32o%r*ndloDtSj<H-bQSG34GWKT2JED'
    'ywfX#<f!bRx=SRRyMPGJYsPBW4z?tCwfV0wBcwZ->Y0R><Tj+uV(9F#S6N-zD<p@I(~}2QE4GrnY<c(wA)-U%j<r$3wa#PAgbY_R'
    '+GI2-0s}m$`zijbtteb;wh8#D1UreiAaq7>lrr_gXQ?Ntb-Ot`uKIyK65rPjL%tLo+Ffrj_rQg~Qwj%eVHP1|dCsc<_Z#$9!^&QY'
    'UL&;hxQ>{!RT<4(7fnUES+TdAo^u7&<WR_(lYVUMCuR6MXsJ)5eS;Jp9F7hMagYtPY0ikzV@f8+V#m3R)r7SsMVN<XpF!Kl?O}X*'
    'mO!uMajU_&a+?(e@%I$-A}i-rKiB2`aD1=$DbTSXve%g_9%vkD=q?))&3}#*O{uzE_lqH#%9$7C&XDEkYUwXgJkh9x4fS`9;xqbH'
    '=`j&bYko4_PjAYlrX$)7@gGOZ_iRw4PPx-t5)yGH$#CeZEyUS6(ah()5}?!(OGD$;E~($gYqx!`elL8F#&ZVmGE*7*T74AB#TwVt'
    'qIxN-6qM8$WSOh?;Ey-SaN>T|e3ZPLtXavT8P%%^)Ol^qRk3MaMZ4)0kQQp0_8(@xxj&hwfUNOoDWs<Bv`Z~K1c$lofe&*IYJIf*'
    'y7#!<RBxodK~V0<RHIGJBl=I6<8IB+;vvHCmnTC0wi#m=O=C|JsXj=G<M>*;zMa7x;<;hr<+~aC3se0iRaloI9@lI{J%yQ3Ld{fs'
    'W6VR7XAY)&VW)IP58bVW8D^ZT3ig2Wl$vt8e}v|gM%u{$QTH1xJgBI1#(e;L7#>;{)ExLs&S`P>{;dgJFe^<XVcT>{azT<r(1b$d'
    '9gg-sY%HPfyK`C5TRnWguAPCUPR<3{8a0kB79a@`$RJk16pv0>W6{;%1l=b{FLmZf)@O*~BX2xP5n3@X<Q(2y#$wpwJH>WJB)?6<'
    'k^8cibCY0RQ4~(78ImELeu2zx`}Vezbu6xx{cGnqHVxD*F5)+lagCrz7pG(hwww)3;hbNYfOj)YDq0wfqh#2L?#n>3|MFdLosQUh'
    'qEDl4aAHh)DyM<YfM=A#G7+^IxF$hQ>l(G1R}?digk)iKQ<SmgipU!T=3#aacGxh}5@>9hypISKM;igPTp_jK1nUn?bd29}PzyKJ'
    '5eeLF&6Et^%Y-3k9cx+etEjzY3BeF2XKKqRVfw(K1EVKTent^-lW$f~r5M%vGR-g2EKJ|6W$7x{@$yav-{nl%=k<uQADD=k)Alv='
    'l5(CRmH!?)YRzAei<FL52_(O*BP70cSNy)#hU1pGxHf^{uw@H+2TMgkd5B+yt)yk}sJI1+BWE$VVpHfWlcNF?O!@yi+;edUzbuCY'
    'Q;xB3@rP3~_xD>dFMZxXyjhn*modN3_m#*(&{kv+W%A~Lt#tQ_4=FQXHMpBdbw&q1rMjrvkbAWaTry7cw?X9E?ayz+x}yf2kW5<C'
    '^AnI<g8ujnPtPtR|9}NmH<jR=BAI!S)+Xq#^TZ&@Hx=f%&f$QrP+D4F4Ph7ANM5u0D-^{c2|GZitB0|Nlh^N8{~-HYK79-#9&xB='
    '+<GgziwX10vWQO1$R_)R4Je1#T7nr}Jb-R!gHdI#DhAbHaL|*wpGkM6Le9%aPjSaaTcUmFy)O4!U#ijNVM3b{ddkp@5_egRb($Xk'
    '{BSp-<6<@iG%+s46go0Zr96#u&@(wPu6UYZ02+sYPr4%U4cLYBpy9sE@}8cASP-(U#GH){kOltirDA_zSYG=rsCVnw0D^2mdYgm>'
    '#Ey3MOJ@|uVJBxa%(_}8WsNNh>;kEDj2_n=AasUdUJLOVEK<UyXUFEW@%mwvY$JJEyG`uv64D9E;=p(8LwDHAnp#mG9yOb9xw#)s'
    'x-?M+@!#Cz!qs?Q`YnJMxsD86BV>&-{#q)M>M8&S8x<J(YyBDIID&@)?<2xgp~nA8NijQ|NGHptIhKx*Cz<*H7IJ>9Egc?=Fx>*v'
    'oJ)qn-TymWn8ld%(t-rgM-%gpRhctyOh9OFLcOz?Lx2*H0v62lH2J0Dej+?TV0SZtnROp?Z3#nil=Xj;b+>v4B%)GO6HKOYxINIR'
    '$-J?PznKJkXhZB}=%o!!x?Ugi?w4BQbVCm;T+kFAypz*jeph9gqv~fllxlOcPzJAYr=kx{;uq14yX8cuBSs@WU?u;J?H;f8w>H)w'
    'JvkO_m8}~wgc?ptR>eAj0KdyuqYV$=jOkPI@f-uDLr_Tb;H>x!aR9da^%w@du7qGq>-00B&3j<hON^q#GHQ28xbD)>skJ-vq(}I!'
    'CnXR3djOt4@--x8<f-X(;eH(i+XVmZ)qdXCn>;v%n=~8emj@FLF?ZC2GaHZJw3mKG{ctXC1lGxE$O6|*8+DBBeQ#fxMJdsei7xzg'
    '<}~lpJMyNx$p1iz$tHALwP=HVYCJbv#)uKHPLo_ft*=$MPV3A=L3<NhiTxAVBmt_<Jyd@kwTT;8UurI=>qq+7OMA1h#N6qg*+Y49'
    '*lFv&2IUWJ&F)fJvK1c9n#|=f<IBLKxeaQf=Baz40eBJaB)WCapOBjXDJv)BgWalj2_ly`NCv54`1$fMDZf}U5$Goh&YICOI&gDG'
    '59m26;-F=B1~X`*(lGjvi_M9hh$8fQ&G<=2-^|AjLx+5_nr<>HaOQi&b5nZ)3&46s7mLCd#s~Tl#JdkrB)Avk_2db*?tXu1H16|{'
    '=i?-X>uA+L2Y2OBM68sAe39}DRx!m$SpkP7Z_EA^q~d85v(9<&yt^w^`O>N3GyWbz>lWZSPwYX9`lm_<64~xPV&aZyZpXEMl!IHB'
    'IJ~0&1cvZrSs=D-TbO)ehsYU(=QEa*a?p$k&M9J5N09x)(?x!v0Ho?+(T?7%VvBHi@M_CDp9DOf;jG~LxCg}d*?QR8VtlTI(`>fL'
    '&A)Y~UqZ$%b*-w!G}eabearz$4a(0kb%YW@mK*-*N*JP%`=~$BLlOTjBG!8`BjLz#yG;#F7k;;n-)HG%bPXUrmUr(z(yu+d@26B7'
    'mSJTibH)dcYPYdh_e6}u%1Co3q;meO=82Zev3Of_UYlMHSJ&G%!-#8@D?I^M2+_Hb*<vyh*ngyjI((ByHHHpd1|heO46E^VbVwqf'
    '$XsSz-bO})m4EA88^(UF8S3b5GqVxNLoYGl@9Emkmp#G(&Uw|^9O2@D(>k%|OTvJoB)Jy-If+W%ut9^}uPQQBUU+oZ^#;d^tOv7R'
    'nh07+B!gK3ym=J=<o_vMER$I2^LyBQm2kp5uMBSo&!@O!ankP4$!yJX1a~A0=`m}aK^14Kxo8^_xyXZF{KeH#P1g!I&6?08EU5ct'
    'dhH(aFwf)AJp#^^nsN~BWROL_>yrtJbyjiRO?~P_%#rMg1ijIzpW%0f=|u?LiKkNW7?7gQL)Afqnu^qBPQa+!-KaG6OMlYH8Ydpl'
    'tSa1=<UJrgqX)j8=__xheD4DxM!0z6VCz0R0IPr7;7J0={IpCYz%g(ut{=UM6qriSkh8C$4pF(dRg#mX&k6Y*I=bnz60?i7g8{#^'
    '*J`g-AqEfWZP6;R&x10ko<K^)DToxZ48%ArPEnJ4DbHvyjiZotN6Z8N?qDwq>gy%=mO#ew*<pjIr9t7#_4U3{sA3hxCNPEct`Iz;'
    '@l>w;`T9b=aYX-hr(O+2dzEv{{i1V%p6vVOiuS9`+!d2ce0VCTw65rq@#=T>>~uArZ&znHW<=JuteBcT)>5z*{S&w%VJIY0)oQ%^'
    'F33Mn!xLSk_5EYh4Q9U2O)@udHHH-|hhB85R3c5!h8`Ra8D~D}k27qryVc340EYMLfbMqc=*>=g%1s$woFtRJJ}1@yn6-r15RXGI'
    'Os4i56twU=FdF%I0Y<x@ljQ0yIU5pL+pjBsZRm%_JjD7g@_7u{#E$Qu1S}Y6qDD}bU<!dLtCjsp^1g1tR0Oq51qs=f5LdY3SR9A$'
    '6R$><t{~daS(!!^u0%Ja_(7gWAlfkH;wd;KrX2MvTD`1IvJ4}arPx8@<w6EjFD1hW<)s3-b#-5IFD+T-p_{T;|77AL@FcHZXRyOz'
    '^vAD}HLasfxWM1=zL6ox$?N_>V%4$5(O?!u)N)%c;o8Cm65QYS7UO~bT6R;^(S;EZoqW#FZMTqZt!a?;G|Rqq1|&UdzvoJ|YXia`'
    '5gGeRH<Z^)q+3&=^oF(27N__4ena-D$)KKf?52(;G&^&c($35o({!GEYD_xV|Gvz`&>WJu+g5;4^wX`zCdp!Vr4LLYgHQhlB_7CI'
    'a8n1ld4FD!`>zzSAK?t>2HfTR_+ZEy-iNi6?M@r7@>Pp=zDE8-msXMTTwEen@JP3p)SN=Atr_R}l7b}f23uU(q59jbmIq^NIg#0)'
    'U`)j>opzd;i`Vl&Pz1|-JvlV-!IFN)zB&B_wXSmy3Z;9vXKfIvxdoZb<-NeG|M$ux%X#r<*FdcWw&{2iA@&O$?1f>*wCK!Eh|RkE'
    'dG`&#cJwu|zT&_O!})TKTGHb6k*|u#h!5ll=Tj$08Ky>Kjm2q}i<Q#WA)rBANHDnB+sLh8jDe1|g0+sY0|+m^W5um>6sZ6cc;XDC'
    'bNQ%Ht#t~LlmPO75*dM^w2yHdl2{dL`9ebo$f_N<nz+$+x7MMeB4v&m<1+)6wi`U2iRg8pQLU|AUycTf$T4WK`#cmu23fm;2YxA)'
    '<?WG<O{H}U=gs<rf#J)4cF$5}VO7jebA@-X#l|Duv{xz@D$0WG<OE5E)MA?1VtU(F;50j6uAUpbWDi#!AVWX+9~Tt4^~~j>U9LzJ'
    'P$Ok9|G=bhO0ZMkCUb|hjR=D$l0p^dHW&Wq9tC5a=5j97*5Wj9xLI8MKccviX%&IgPV9f^+@bP>*ovjSQGhsNj7%=b!B)(i@9BD`'
    'a<>|VbB^2YludzvWv;Q+f8MuTkz5%5WPK2bS%f<?xhDV98JRJ=gMi9#liX$SIT%=q^#0ny(vfotsBh1JPx7ez0w}^zX~l5T$tGAE'
    '-}ywgj2&a1#>V9*ru@v(Cqo+}(r#MO7Mkf1m}IsC7pqqFyEsP@H{{uu_?tt)xs`?Z=vsp7NZ^D`#C(bZc9ftcq?`I?;7uf~!G)WV'
    'Mv*syDz)W3Zn>;hGX-EsblXhtm4VSB;?cCrw~9ckEp+Q&^`gsi$}i?y!q^loUs0L(eiK3jNGRvIgVrt2kkt|Ec|>efW=!hpPDP44'
    'actcO9epIvh!pu)1x04xFK1K;LFn}*X0}yU1x!Wn$Sdp{0tg!f>_~!}Dk~P;!(ibS65U#sG1@)%EIwP<aX5ueS?~P+B1_iDZR(wb'
    '{2#+;-ZnaSh(}-#7zT#JYiT!)!YpE0ryp;2La`1D=jXb^{WgWtn`oo`IafzC9#B}CwP$k@gze)Wj(+<8a0Fx)@#=S-)2U*$P<^+k'
    'qE<g7Qz6vK-Pf|Kk=$aqRBIqzK;FFzS_+|{!uGt1>Vt<X929&TCV0nI9cZxX&6FP><*X`EA&BwvVgfq){kHnc;55f|!%??Sqeifs'
    ')a6+&it#x^Vl^u>59jtY%Frvg=)^0>J^*s_S27)u!fj`i7$nvP3YMOYieQD3^E&|b3i&56rE`g0;hI1+14)2zqie~Ehwu`E>|o=h'
    '>^CcdaFcEosBfH`p!{fC6>EFzFZu%#z@QElF<bvh?B+5EQl~dn>KF_7zFEcQx0A}rd!Qu8>c&Oy+njmY%0@To-F>}WZ8_RR2+g)~'
    '9S-GY(0*f~zMyn%3bJ*Pt=`!pxrv+P8&Fo5$@>JD2$xtFsw-F3_#np0#vMgkH!fUgJrgEKm=en$TJLx^@*6Ow>VccnR@VV^;U7>F'
    'IBmbx3tp@~_A=H1IxhQbX{b~Ge6`~DjR?Zi%Idre{>+yY$S>;>_sKV6i3H;An#ljI;uE0>EhrDuQjgJGC2B9jB(N{D6LYq!Vj$f-'
    '{@E^gCa!Gdw3=<exL066zsBn*{131e4L3gzpU6~&H!VMal``bi;2i${?gd%=ZLQ`s^Lx#x##Oei|EjkQysy^$q8t!7qICUDajR%9'
    '&ws&8zeux@LHDa$6b@AeW(Zmg7T<&*ipk-@fWH|3vS!EP*xL;?&6x+Q>W!`iSuNmu#taA5H_lS=+QiBDVgLXEK<M1Hyh9Y_{d8Gw'
    '*~mBD>v+(<N`fzzQA7M@{iAx7E<$1bAQh`9vAL#X6e}6#Gje@F;Eld5fgbp4rXt;h<pL%ZZ}97lIF5YPR6M?`<XPLwBczOZN}VuB'
    'Xso%+NvS{1(e~8f?0?W1BOmuOwszu^S=?-@2RfAy;8=M#6ZB!(vAT;;1`;ziHjhGfGf|8_d8ed7P4KDJx@<FYtAkE8S`O=!_luC5'
    '7wyfxc9OUGgl|xFfSdI(C}|x3V|<dyd)x&A3sfh{+g+TSD0`Hkgbw{Met;w(uPON?L>}m-B?tMZs$1>`nIyd<va*M{rf^ZRD?`e<'
    '5{$mVnsd)`SG$EOF&!)P@CRngP(Qfx&O%Vja=mc6bm!vthhl{n=Au<ZTq%iVj_EaNnkRPcJhPEnC*H=f{mr~&kwT)=k46+;XpM?Y'
    'JfHEsydp|*H0r%f0n~FG6KquCIQkCPf|KJITz9Y#C-0Hjo3jnSCjEw)A^^7dVeKNJ|9>L(saIf)T)l?-=}QEZhnSE8t^w!`3}xT!'
    'Ub6`^-{SHW)4_USJCGSf2p0oHi(|Ku{rjXhc&wrUgm|4YIn5HH_4whjVZ#jirf<_kUJminL;{ciUuGc#LWL8lH*sw`+wX641TG~j'
    'R!+HI@vaG3o`3&!u@toFfjYjZk@TnS#F8rY#=M=0wqTs<7`<0tpZzn!yfS+}`Oi9FN-O0ctg)Y`Ql!n9OTvE}N&0Q~<jp}2`Ha!L'
    'lKJ>Ytj;xmH6m~{gqpd8(6ew!DZ(<7l>R=z`fW>QVoPat(>51C9KxnutIu)hUm$_^Rwb@;ULG2Vb*IX7gw)hc?aPCEa`p|D*k~@m'
    'mZMs|D(JIkOkb|=5hALMxF9U)<ygo@T>#eXJmzsXyB+{ZK>g2g$-u~qk-~CA=fQE!mgQX+feR~Iw%1O2AvZ8_2$I^zt*vIla~3<m'
    'LK5es0EP3zIg$2m2X`%t3^GYHyjltawtvowui;<<bvoNj;Eg_{>vQK=zn#p<_2RL)OS7kRr3jKIBn;S+OZj=^lToHgc8JS7`CxY='
    '(&*~JQl4c|ymEJXu+3oQm?)G)*Q%A+Ig~s-+W7KrmlRK^tlms`@?HOKXIh`u=h+v`u6fn2o3N}l3(%1Ex9=9*IC%+I)``E1Lct9_'
    'dYc0}2_8yY4d&@w;hiU5*STK(7)(miFP9^1L^MvWgm$Wc@@zZB&22SYtcFq*`WjZz=>h5KDbL@yncH4D5Up-73g6HTokvC3y~Y0*'
    'eI8tvC#9^Bn7@z%x`NlAHtI2aB_ANTMiLOfDJ_9c0{7q)Lk(q9)i-&tBJ#!pOn0eK6}OA`+(}uq0_^yeT&fh=Uc_4@Tt0*Ck&q2Q'
    'u_RFG+XRtYDH@{yO%6d2X)(4wTYVS(r_8i8a}CK!Hu8;m<NrOVbZLj^nxKpd;OXWk%{2fr_(Gpcmw;o7Ij1hLCt*Ns3?77q4rVgn'
    'kpdmwk662C-7ut`H3~}nf@fx_f7;gv_JmLI!(Hg^b1wlL@{x>()}ac-KL~27D>)3>@^Nfosq3gy*8k?IT$kLp9-KwM<duOngkzZN'
    ';K<@JBt4tc2C7LPMr4_5%`&oq<&-KnG;C+Jren#&S19+Iu@!WgtXGsD_953rBSl)hB-aX1uu++Bib?P{BaM8oWtt`4r#ncI-U_G0'
    'Y?@9hrv<W{@B(;Eg50i@xC@dEgh3lBzn-8G@`i0c^xw`F#T5>!$&7)pB*%FwH0HjfYp@JqTX64<5a$6nIM*wk>4b&w)FZVruQRUN'
    'F;ibf5*hj({h9uzKQYA59@qYcUAX1EC-$<5>j8I4gypbRcI_hd7ZBGHaFwI9Y-z+BgXY&P%~B;w;rE{ZrwrIUwG%SXj-^7e77DKX'
    'C>$ic9-)X1_>Gc4d|P$oi;g@^s7%B(vvWp$572iB*L1au=VaQTtoqcr-Gx{&HzX5ZI|J}&OX#7ZU?^FSW*EZj!)<hldi<NS4pK_('
    'zd!7}N7)Iif5w3@#N(4W3KzJhQpzw!WT#pDuR8WkS8L2modO<a_VR;9Vfj-oxND#GE`B<jINi+cXE?82Dgv>gVx*ADug_7%6540C'
    '946UfbVZ(>(>VajT1-CqT8<$qVYt~CN3{{n;=1;cu97spG;R3BS}*ybujmWsQ}cy<(#1lA{u*5wf+nO(KFKG^d`i?zLe`&x?gG<u'
    'pLEU)(-9v?N0^l4N%+Wgy-jE1;bROnm>u8cmf`0FOd|u2e?iR|A|_XaFeF;~UEkXzg7uW=Nn6Af$CYv$G-jpe0tFEd5B_z2Ac$<f'
    'J9FaA?kS3PhT}R{XFk6rf5JuEkn;zC`~e&iQ<VVc>5Xk(7QG~bD!DA{?-|x6NW>*|7|j`j;q<g2-<j=*dnU2wm8=u7Lz}iQE%+3*'
    '-6lLcarv&7wM+G;k^W*k%@fZgy6782^n(jyTO5T8zrwE43hkT@jGH!Cfc-%1&4)yLEU30Oy-u;uU46Oq%qjvVkZ9~w+&9Gzxh|Tc'
    'OkB7ZIeTxc%RDO<XD@wFxD#(M?cvD|=7uca?6lJs%$+-&To_XtpKZgkk05(uA%bjOf5IqS`d>Bt0q$2Hed>`Kt#2~3iuvG-MWnm5'
    'x{dRI671SE$WPcUjRz8Az)VAMHM_&O*0gC;X%m2>7Qnmd2Q_HaBS}fEC;}h)P(HKtoN*l1tORixmXr}i1%>;VIP@b@7g^5c4M?po'
    '3sFPpvfMbqNJ{IZJ}S>%vsllC+|_2f>ngRAV6rTC>3>OJ+7{h!2qVlxzBW*ffkcV~?xFSmFK}Z|#+)%~F_2iuY?YS!XeuP%A=^LT'
    'w2nZmQK|?7+mRn{l2C_{HNhaZwsSmPhbH~qCdhE;#u?@PocRZlf!lZ$0tYHielZJvUFAm{C@?9zh!z_uj3U5e!s@ZR4hnigWb>gF'
    '$2TVy7l0hA2nwZHQM~M-(od&@&cMA!f}+y%2>%s0+1=1Y^5E|w<L_#U-Q~y|?8h8SvZ}%8V`J6l1>7~>_{vXVl6tHbb<o)1Z5U_Q'
    '{+v||n@1jLHPXv_wJnU*bLLa0PT`6M8rkI-SY>*keVJjK#+B>J0FO!OD%wYr6`}|&MT{&74TCI+Urvb0L(bszRIJ&j-KEhIf#+|@'
    'MDx*1xnA@+@W(ogDvqn1XPh=z=O|_glNOG~<DXIO0gB{2{>FA3O<yi>YNGNsTVcvstf%6{lFh+o9sTu-)74_R?_~Wbu+KlIOMw7c'
    '9^@E7D9tu$8dC*sMF2a_Fkive@<y0XdCRIZP%Tqz`-c@C;kceYjwW(JY=M0?3u-aLb#Jk4#E{pPruSyRgU_W@Q<3TSSb*&qF726D'
    '`kzg9>aO^9#ut*YIo53$Vw_<ljYq1~1VM~>q0ywmN24rQRxw^hl7ksuXU)ntJehB)8@moK1<8X=br#aS;u_AC%n#C8V>=Pp<n=aI'
    'o-Il&67HRsOuFKR(J){w&K_A-p)LqkH;0dRLp&I-2BZk**5MDODS}A2UK?iU#E<vc&FI3VKyrzr>bO=$4{5sv7*o8VfFPZSh^K#P'
    'fhuK>J|HHU%zZ&DprxIPUj0!vEXhqo70pbN;$}pPVM@nZJwYNlI5+*kXw5tEAQhF)QY@^IiXlr@Z)Hc-LYW`)??Dft&zNR%bRl4d'
    '%+`uRTKhRJpu%;Z-?p9PxM15_8Q9UIggvMoJNgIvaHPP+qwC-L|HA3WULK1UX7O)d050Kq<fCLBi;i6XRAd9P36oqt6?h`LwRy%N'
    'ucPqv;`!;^vDbN&Umb_~OnV61PEP*7yKz1v)XV(o!(;76-zZPeX*szWplA*69#_a2n08P-UAoT31Rl>;)_BTtG6~SIld#K_0M7-b'
    'd*9_c--%dT_`_vAL26$_8A0&I_jOxt>!nu^0*(Pt&dQ@mESd4#yZyxvMBnFAN(0ptol>jf#1Yvh`LH>Oxdg#IYerIuqoXsiFD;TA'
    '&c}Wuo*K#4RjKv^Ga_Umu}NVwq`d<GbH%vEx3ZpB8rohp64FEVIE;z9)29F$TgIGdKA>cJB=_WgOtBs}?XDL&kW!>`)3s*;b#<{!'
    'I63VdX+v5IWNKN8y@EvRkcm@YK^+??%7+x0<;9iw3U>p>xd$lrw~I!Kg50P!RgmO3ySc)m50^CVY(o^$U;Zerwo=LQF$ki*y)c|E'
    '6)K{4t`=^utsiIV4EgU#B3aX^lWW}Vn;WPk+B_KV!YL7nPdfdfmULz#KbxUoS#>_NGoRpbiMa+iAJv2j`e`m};{YKGp@Yd+s+(?~'
    '^>4U@MLLRpmYHoNZI@PM<1u5s5w9V&>t71(6`Jm(eA`>KdiJ!JA%n)O(7d%@cWnkVrNX1ogZ82=yAJ%ny#c=|p~y%v`(pQ0wf;iB'
    'j7L(IUg~L4scFESi^H*2Ba{gdOn7eP;Ucjra#6P>RdY0W$UJbirgFO!W)QYrJFk3^*EauN1qNb+8#5z0y;x@x2NK}HZ@~F<arhrr'
    'W_b#ky57<;7}f#}J$LaDg}-F`65R`(Vffc$IV;5L%hkHl{P|{{VsYMr@yo|bh0=7D)lw-@0Eo8y1i!p3w+qV8Lq9Q(<8AbZJsZ5N'
    'nVdz{xRv+o2QxkYm}cw){eE$UoE?4OFi1SywA@%@#D&}+O+lQPr5`U2QzYV?oE_#RQAAekL2f0rP_vhs0_#s%M-KBb1HtAfd#cZd'
    'BQwHkB4z5>f`fS?S~fz8p$E=1q0lR%7*zR{v7IXcGz^KO3xSk|(`qx6Q7^|Ey67Oo@*7O;T62Cl2@(0JghC$+cat*7@_{&Eu;!!y'
    'YtQJ!?+!*v9ZC@bOds!KrWKpc)Jc#uoG0lB>j}kh(M$H+msJq$vJXS0_L#vK@rH~Q`h^gXU_X#)eAr~x4ba)MV3cIL-U>q!_~%@5'
    '4Gf+_tBtF|BjgU=`n!M$8RtLQlo`iVgCliQ%j_A~9c<bupam;;{Ldo;a0^hxHy&bY0)oqMS!Ff+Cv|jwHIw%cW;$kWwNyiQRMGxr'
    'K8oI^{XLbq{EGee$_$sOc3ylR*mTtCEx1PYM<RfDDfl=ns`%*KSFHC{tOp+@S8_jd3HTMj&lHv-A6TpPUG$fB<~>5p(9MzFD=Suk'
    'qCy(#nZt+zt05P9F!{D_qepo!;`nla^ZZRsie5iKN@{d8eo-31%A|%Yb%;T6c!D_I!2b>yt%~!$vSOj%G02PCEf0A#fbYS5gx^f@'
    'itmJKo$S|`srFg*rcwv!vXB!&AvF<D9;q-Rzd&IW(>jrcG>tQ1nK(?*)VIv8&G(f~u^6vo?D|({qGEFKsh;m0{knb_kDktnU3C1v'
    'Y-ad!l`SKL`#Gi*I#q-z!e2&>TS#WAeu}Z>84Kdo^MkKTJjKIUu|+HSQaTyYuY0>o@nbN_HV1m$BQ#$-V(blq$+2h6l{!cK*<K0R'
    'pk8{$liPYAb%;c62!4k(F2%$Xh|Ek28Uvz3$u*9SF}@uL^-*C6R^y6$Nmc1>64dyyz{c00yPv@>lToy0>Cf)JnWlp;`3U@}D#a47'
    'KN_W?MG&^ByNJdW9p&XnJ0W8PI9(~{i$s``?F~rjHHQ|LWdMJ_<w4y)|Ad!%xw0Qql3=?~ify0M99g+)Go`iji&#ogZhWXLa-27G'
    'j}{0%JP4Dp-+{K5QE+3pVF$bW5DUIkH&7w7%Az_sYcmgg-kq<j*YZn(ljGCp<DB8ZnAkpJ{_%=(t(yBKuW=Q|qyI%USkd70jMb72'
    '*$!C5WJ@kHQ@4wf!dBA?y3eX*tn9IR7YeNzT`oqQR{q9c)OP&oR5A6}Rt^f>P*edZ&o-#!nl6#_7cS+NW<=TM|7TezKot%Sc7=OR'
    'r`>2?Wclo$o-z%q!>Bk=*x^;(^F64qWDzV)S+FJs3P|`Tl)H}r*oNd&I9W-p(c#)p%Hg3r=u+J`&nl11k$uu4y7@g@`Q#sV9s%m7'
    'iUd`Eg3hc@&OV2@hKtT$+T`~$&DyqI@VO+iv%E&xG#CEfh^btY^BikWMT9oD;KS2P-WK$#e$fU#_U$<qL-4;Q%Ge!RA|0I@r2&j@'
    'LUBSIAw`_`?VJvmcyynX$N2f#f@@~4&P(E1^QNetG1uyGWFklZClSRPbxT_q8iCCgrMWKVK?mOXUM;d)J}7-``ybr7wu+`XGKt47'
    'u-0%Bkqmekth85HDk4W{ad{>I7UCSf580T^m7OIDl!5h;-}&^7qpe$3<4fT(4_KWth4xszQLj8QK`_1reIWY*H^b1}2oo+|3Ujx|'
    '(ZAwKdB@7$=sIXyQ;-6gk?|zPxxc0W`qV4P^w)b%AHJ*?=b=3Zl!SWHjoEl6nYoKWW&D%ZC_NPxf56qyIKWYvdzt?6hPQ;7587eA'
    'F2UIE{VVt#FVWtccyb`gTCJ%KSPlEbuCC8bRzi;cnVUyy&ZX{;mrGAx1#MfWg;|M2ZtXQeg6BKJFn^;@g|IBX44-rUaYM5tro>n6'
    'xBOJ5_`AZ14jr%nSH*riP;tc(s3*Ntnqf;{igtQg?JO0;aG2=BXqv3mD9$HZ{q-I_+=wp24=4X<enQdi4cnA4SZ8(OsH5>fNZC%W'
    'X>?0EBH1crk1`5<Zd#xK-O10CXHhXzU#Tz#Wu|BM?O8Kaij_!D-JvRzUob9@Dp3DUO1N7KP045$cqMxTQ>zLM(ISrw>AZnNsUv(h'
    'q3Ra=*~k?#G$znhzht<T$*HU@l9?K1j{BGrmCle^g~4;%OxA=W@k+TYLKZ6XMejXM1l&N`yhD<Jg+ZL*YO_eBdOGpiG`I&4eAIdf'
    'KU8>@MlB47B+L}<n~>S3@HGLI?Q0w=zSO{~xu}jV1B@VE9&pcp>fL=G_dMgXWTrwu@rB~Ol&hjMJVI9bE4FJ-HWWuc79+fyYcZFR'
    'QYIzi_F42><xA>lU`g3*qhKwa!<H6A(UDZ*b2Kg!dm{=;<d{D)?Xux*!a-VW#`VxkiU3v<n6r80i(@``#vTogDa`jqQ->oQc0zFh'
    'bH*!Gi8O4(+=tg>2r1(KePgtcmw{n1KlN9G)sKAO#7~bG5&XaebUseF6{~{x9YPx)N8-0>zUo!D;-p{7)^Sr5M#crfL7nP3vI?QN'
    'QRt?Jan%aNH<BYbspm^SoWk7E6cTk;z&+G4dHP8^4i(1bPylQQ!~nH;V(vKTs>@<n$JfFSw?$}E7@c~(I=x_6a^+Xp&40X$?NHDU'
    '-7^b!<d7eXySlm}(qLPos*mfH$`hQZC_tbKWTUhjD!7{t6=`T$NS?nyK^i_gNw|c|v8xVSDPqeJ3lo;Z!-eLctjAoy%t=5qq}0Jx'
    'gogr|`>eJ?I72F!&sWg1r5##s9pAFQo^(mqw<qaktNmb$!KkFkjhJo8mNR1?{OUF%8_SVp9O30`%7fdA`hA|3ImuoT;H3t^DUZnN'
    '{iV;hmF(nt)lSHu16m;;6<MT|cXxs3f_<`SDfPGzSPVat8Vq9y<Ymupqd0UpiGA#ylTt)A;dRp2?fqOkKK8JOw}0q>pGEW>7xf6W'
    't|Kc#g4n23t3m&(fxX(bIm+!uwoRG>tacDbP7~G1z<du;>*@eQjZ8z~3*?cbGvJIG-69yxe}hB}zA%RcZE+|6KZBrqfrU;aFCp72'
    '{z9XcyyYyme88vnTf;*X;M(<v%N*TYn2#dJ-02ht@VPTtcvW_<_TgneBB)PN9Rkgw*|IrQos4he=b&)ftY>Sw$nLY`f3g|xI*OVx'
    '_VGTtPSD?9t6hQUXeztK@JeY~;q}_fj=v6dDV|oZX5){xvd^r|p+E<<Qu=5Ds~wB}S98J~jys;*OU%<_?Q+^!DmxzN8$6rXl79f)'
    'Afzp$BMoc4Z5BYVZ8Dj}fOLe?O6UR`H<!S2Neykbz_XKz2pL%gNe|SeSQ55G)G1&@P&oozG-In8=>kKFF}USV@W!hScFdjO{=G`a'
    'N4z+s^(fu^ELYwWqkVtM!aB=$tjH<vcx`4;!^N_0?k?Y@9cVR1U%BiIi?3IrJEj$qs}yo*`$#K%m%sfNS5u-`|6UC4UBZbh5ogHy'
    'G8nbD>Z&|awD$Ua#F#@ktTKY|tPt0KZBO0Nus-J7&dquoW!Tdck9R{@!QHadnr<nXPe0BtlC%>x|M%fs6Of_7D2BJ<oSU$-IAw_`'
    'bcwOJBJC5-y1f<{Rp_V|cgJD!G~UY$`HZ;9j*F}VEH*be=CX|?9uY?Gf^s%MLuBA+jTLHX?S9iV_BNfY!BSd)PY4WYCTnj=XlMxx'
    'FeZCjSr`NKJY@rv;$Cle3cIkaiHUfq0~@R`?$@hOyy+9Rj@s)T6u@+Ym4T@J2Mn!%!u063{63hNu4vLP*-{ymVpusLa3F|MA;>)K'
    'x<XEcp9IK&)d>%KZm#~o#R%Xg)SyJGJf_ZW=P{Nd2ot~rA$J!O^sO}$)6X>9-vF>BhJ=Z^JAC-~L|^Pj2XF+HC4qGmZ^!rN+J(IS'
    '9LVMAXVQBMKFj{#?_mGgn`{RZTm<qv)aRF$Ud+XTV&n@uHD?HAAA@Jx)5_uaRXteNF5qyY3>s!su$TU4%&&D>v>F8wU;JDZ@JyGW'
    'BI66@Q&bHs@;`m3?qQarFW!1{fGQofoU30^Z~==2BB~8>6p_HrAyl8ITaD#VLr6AJOIuv4VbvH=(wfc5;jH8S2U)6>Yv&T)6ORB?'
    'iq>jESI@$Vv>(BD05UBKQp@*MSF1UybgTo2xO-hsmRHwP)ULG&V7#;v&}OfmEEHeE*QH9MUPIZV!zh;b4PB|U{Ge=o2znZN4`A7&'
    'c-}njMYQ6CM!GCbDSkgk7|c|LN2r<P4o9ZK7}OsF2IDEH6b-@M!yBs5S*IS9OW~eMPJv5nyL~_%#v9d-YYtIjNdgHN4j-1?!*(Z7'
    'N;`27!n_S|Tl4!jkq3cMFw0($eIINm{U*RFOa3AV0ly1BIrKhpRr(AOH}TF|C>ru0cL};N-H@z=X>sMQ-~pf7fHV7X8IoK!0;w5D'
    'hXJbNW(lt3D3_C_C~LMcF|?qa|09vK1hvxf#~$)a#De4P&HK`z;DNUKw^U&_w-f1%K+S+7nZlEph^<mtZL_X8Pf#<#=ex)I(@~v}'
    '7~Nc!&YP6Kay%`eg_)!_)Bs~-k2axOK3@HoJbQWX3oA(R2<0n+RySur)f$RRI_@}ut4G0gL2jan&x~#GuoP{Ap?Bgf!3eiD*NeXW'
    'TD^GN=Vr2U+?G@x-RT_aVB2t*8mc!GgcRga&3j|42(L=j*6u9Pi@Ncq0NFQxZ`}^$1JIJ$Mer3rLj58HLV=5uhng@cI~}=_)2^ZD'
    'Z;LT}Yw78gA@<KyGi%yYZvfGeGm`UrKJE&XAIFZBAy6N_kmta+#twto7600Zc@sP_PTt5L=Jl6y06n7sfbGxfr_C&quByn#@RTB2'
    'UOdo6aHl;{{3Ji$>$&rzx{Qbto4xL1o4Zv9sApM|9+(o+M1l9%YSn=+c#*Rl>fyXU&v9{aM^YM|ovunAY_z_WyB0eBLD1KIV$z6x'
    'I2_qj>Q{XGQ#SWt66T_}dCGj9H1WGBbO|N!ED+u5z#A|9%0tFuD>YUhB#BZ<V*zj_$M8ROXQH@{LO;e*`23JR-lg481S90!n@&^y'
    '@*lW(piNT714MT{tgG3%gSfu=nttzY$Bh)n-9jj!lzkfs5%&G4^9a<?c5Yt#V2MR$V}mM^YhgLK9^cAgkQprJC1s;D77@rH0X9w`'
    'km#Il1TAYK<--Fbp;C~Tgs`4j9`NcikBR&9&nx@EP?p$hRK~)pQVieVlWdUnSwr?V0`z2&9&@1?zLL&x=U13je)RSKwT=l@P7)79'
    'L38)<Gu0IctTy>p^zV(TGH3dCPqTX#KxbmO<~N?5A#<+*HxiD?h7CrE+{&Jzqg4JLf?^L&(Z#>SagR2*kE+fPSrCr(Eom3*ZQYCf'
    'xo>ynLt5E-YE>aniWDALR8_nC=aPP8KbZVn9o@=qBUCxyHBo3>dy15mX5A#~T3;UI@<?8#F5!MAHdxV|oxH6{44K7xohwE<5aK+M'
    '3N<UpC~Y@<+@Noi9xLhIl8-a_D))a^Sb3ub6GSl>qZ(6}Y1}<dajCT(Z~Rn1K*5QihKQ<TTX+%8zhwAk4|mKE-{z(!f5;QMplZ;A'
    '^D=>=`B0RF*pDA4yr6J$V2y3J6}Sc^jK9(;)DkpCM(}OBa)~(+pe>-h0n5VSktorva>t}ZNYT62?ruJXdiWxX1vbM&XnNpW+P|2*'
    '5*ua3Yl*V*)n1dCE_&GHTX2IES6t3qRc7f~DH%oq@<N@#?>Jm~yV)R#=<If(Jfzrt*4f7X{22DzuPPMOECf@|VBCzsU_;i~dCpv-'
    'jZ|3D6Yet1w#gA{{;){ohs+e3Re6p(PlZan+@5R|`cBB&at+>V4*cP9akF%t@OVvl$d&ZZ`Z7jXDRcj0yK+OtGXQn2fyVP@B?h@6'
    'W2H@A;WImJCxk;ZVV|$ti~TEbs>H=y>hXr<0_Q~qG-=Bq&S82;tEJU8-{x4*zv|3Ww+x=~Rz_KUN}4J}yG^aiW7-^%uj{dVMSfWC'
    'HN%dxDD5nU*1$<dBI$sbyQ$cEewfvpG50rvt}5(;R&Shz1mnpPhAvI5Cbfq!FM<|XgY_^UOHyMZ+K7D64nhoQKwE^ylsTYaL~?BK'
    's&O{b5!mgyd-!7N0upyn)~1~k8^MkrftT;kR0K#+x=#OuO{32=dur3(N*s^}-Rn&maV?TRcu~*n)_7gb1P$x5d^|6_rzX?a&-Uu9'
    'Sj3CBul3KUKo)MvWScifToDp`_E{NdJx~tgmEEA*-M*?~yu(xFUa^mW*`+OL*2r!B>0G6~P{k)Sz1mJUe#)3Ia1!2d+}`fDXN6!s'
    'oV0cPV2ajn@)i42Fsdfs-GQO1yg^17iFTx9g@-Q%K#8#zcSI%5pKJMm4qiSoKuKPwdJD*?os=;qWYKXH7EMbCMm%$3(>Ug)44cU^'
    'W@I*zVmNc!VIVwY45OXN+gK3LdHm6!;z_=I$J+aPoiH8%8!gIU!+rj7N-1>RP~%q{f3Zt2^$F7b`hC^~oj$*9{H70?n^FyP3x`{*'
    'Wp3>JmQt(Fxcl9HXVc{!-e|0ysn#EYs+Qs0OqqK`1V&<kb_=2p@f@N-7*+Z7eCX(2TVXd;2*yKyDT^HF<G>N`UFfg{ck4|JuHTNt'
    'rK{%!{HNphd2^27oy6qm#B(@e9TEx$fj6Lp=!1|#TZ?~DKoapPKX0G5B1$GI)x);01?KzZg%(Mqg38!V{Eop<x}Q<mnt!9)!ru-X'
    'oCtL<N?ylN5XJ=5y$;5p0TX(IS1e7tCgR^@=-#`=&doS{UKN`uShip7qH=SZ={~oU60L}TTBQKftdjj`UN0vv0M9qo8&?5x1CM?C'
    '$Tc|AOu8?*SAFra4c=>C{!!1~a=l8#Uh^;d^dWq1811&r$771Xf4%#ziU>>|xST#)t~<kcU>>xXiz#R*IQr}|@(4!+@9sIOeomqh'
    'pc_!Tz@*<UoWt{{eI+6eUfetA3@uTn0|1uc_s__EpiT-v@{^E#cd_~E#W%1JH)<AH{ZKyABmi6jNjj7oXpeSbku|L10Rlv4!=SU='
    'vR{hKmBn2}@*aa6vd!IusL)^Af>dQDyk0OIZ3O$MvoaBD-XW2>tAF6ydYn53%F*xVR<Zhk@U#vnME6!(h*1h^?mVtw1h_p%yjSb&'
    '*#02uh`c(Sh&oM!x_i}OrV5%DM0kYIu+7oC9n-v&ExH$}ICtNzU@6p%>n<ERy8rk5j)>Lr(ivB=Wr6sEIq#d4v{K()zi{y=X?Cb;'
    'e$*Lx@`5dx=x`d9Nm0{_{aCHwBP;934*PiFZ%fDW!X(zjI(i}W@rh|}@-6@M>7dMX*7<QxN#SY(QwVd~+ittLH$<$Q8^7=gEe*sI'
    'Or-vCZ4ccl9D1$(Ofa~a4=2F!MW2|NQfEkyQQ3KFVIMW<1brzrlB<Ft!-1Ey-k&tuaEEsj{>8qUShaqy!0-oYKhC(PGL8;2TrJqx'
    'hPEB4Z*&qr2;;FY4hNw$tu>1AYTiq<-+H|wx}r@iG(zSL><}7i2!fTgLOP<7kGMvtv8OHfS@}Hkb5%$*XJ>!9mXTryc)$Iha)nNo'
    'd`&fobHm60QmYNdHn8g5hbE^%=VkgQ_=^o|Np_gN9d*OwhdjPD&orHu_*RX6uDY=uD`x}%_+)yQ+QH6VkS4c%33U4SB(f}31r!IJ'
    'vg$Z6)o9}~A3OmSGk7{qi#RqnO&>^bJPxK5ne;-~A0aa?>Mwul54o+KmdHr79(qKY)8?tXKojyzuP=V?89M3yUTt1qlNJpX`AT!1'
    'Plb(O?55WNxSs0cy+c4vt!%TRQ)L80OND`g=g>dWPFFTf>jqQvV=USe^~%`tBKW|7qjr?gTi0&hu5IV8LHR5a6v=^M@cWfHv<ge&'
    'Z+DFiox<TYYX+wy<wW?guT5h*c9mC;*c%t6#6J~rat^+x0IaBha>sdqy{ls46D~X8{{wl>%#i^0tqb~lbbVaGZYUZ3i}lcWk}VHb'
    ')6r-sH?k$A&)gG~04zc91k~k4A-#uzE(h2W{od+V1^Y(3(dEnZGKeHcI55K7o;Eg%4)@GA;b+9ZY;MF01^2xvnw*?r@dL0>Y-fMK'
    '4{JH~$k3M+d6K0Y(TK+Iu_F@fG@Pg*o9KO5k=lNkS7{KV6aKY09a^!IEHmh4Mm-8tPI+y|FUh35{w;x2UpjEY<Yj>PB2u|3GBXqc'
    'T1EhI$Wp$So#3qfM6g{SUZXHBKZ8U$wI7;?YygU6>i$MATBjQ>u~cXCkW_@Fg)I3cFTaFyP1rp;3fQcXG{H5+uPcd52#}h|ZAoU7'
    '-}^LFDb-$zNx<OgyVna`g-4^jPcL7Y(aXbnE4;T^)57dlSi89t4a(6F!lbtR_!yRcL=uuX>w$yYT&_Mp|HWzfi-qpVmY&^RN}+E^'
    '?^YFAQ#QprCL$%Fi+EG6Lq(qq{%`rmlA!u`kp@nuRo50F*9UWJFpe^`?M+B)AIw|nT1{%EjcHAui4uQr09;}HOAApEDUIrFi@?t!'
    '092-=q+fYo>8T4`rPsUscF%_;%E2i~UwRRrVc)@uo#4Rdout<qv-|^$-^1c1#=D0x?f;yF%yYF;bz`pzqTmv%;D+M78Bn7E`>2tQ'
    'ZLNLVLA3Q*=`JMAh6<QNQ4$LJV~RLx^1Wt9psR2n6(X<0>1SHI>yulzi1}gK;fEf%_rE&%JY`cyhsSg8$hU*)4Vqw?y+o8S1De(d'
    'XQmiGoC_3xKUkCIdmrJ^XQ_VQLj)&^`l5e^DYn&ub*0O=+@>&|TozsBPL~SofZSv!Tf1!c<RcrUY?&Ce6Z=$0J5mGd?B;_X2QiNA'
    'GB+HtxmxaeC2B7+4|m3I;=uB2o|`r-Wu6rDJ;k)lDn%hTW$Tj6#Dv0d(M<3#AFY6n+CU=u4x30+%0_r&++(kCLG97eH)1J<fi`vq'
    'cUK{G<fAGlzac$lV?7viY!$2rkR#1(z5d(Pg#jyzGOXA*(d#k@4D>MDuvdK+SPFtKegP$5NJ%yq2%W;y<l3}R66sVL-!|CNqBj=<'
    'y3-m&=Zhu!5n<Lca`*S`T0T5N>hudg_s<y{*VhKzKRAuE8(Cf9I}L)qvI!?iZ-s0#SmRT-j;AVQxOb;$16>=5Zlh6ZFAAN$WH0=%'
    'YPx_lW3YiKVuL91YdK_=Td{cH+{%$l;xq9ddq6m-LME3a(>vr@+|$6+^+Ei42X4eOU-!nh;R+FHR~~CgStDU_h{U5r7+v_ECCY;X'
    'mBak%7{f*~vb?()*eX$x;H9n@!qi%;g=D{9$E#-NhF;#Zdqm|7#kV^>2U^0PnUAB<g)hsBwfGVRmOB<I-%)Db=`fj!B$P{h!#Sev'
    'E>0PBrUdo|J>dJX@%Y!vn%3<II#kReJ=HN*jEDWRgZb<fYx|#ZRST?)fBbLu><=JLvH*_JRFBe2Ix?2cU*Dju24Est&mr`VMCTpP'
    'OFFE(W}LuH-+1*Ep=c8}IFPq|My4&)XB@K?CHOTvZ4Ys&whB8Ot+DL9LC|A3w2U8YDUJCG=s;&GbMJS_7>+eW1d6%S5AlwcF_qh^'
    'L|glPw0Gwg{R*Jfh))mRwsQAo<^E|$;%Z;cpVuzIqsRQ6B9z-W01$SPc3;9S0K39;7zKIe$|23n5K6bp_xCFLQc{GpwwKJ&zL~Ti'
    'lET??WlA-L=_0y|X>dBY^Fr1yYq-T+8#Hm9HqUlv)oDtk1&WmQ<FsClrterl;hE`(2iZ4K^oQKtJh17kl4X=gEN)0eDxav}VQ%5R'
    'jLMYojMOrc_UP_bj%J@sl1v~yySM02;t`_O)(OAM>?0!n>Ml9z&%h350Zr++wV57am#;TOR%-a(V>Nu*%B?grDvK`D>RgW`E<sug'
    '7jeIt48WKAR8svVYl#%{0Mi~%mJdQ)>L+?r$%2p}x@$v_?0~I%$dpekLk7$y=Z1(Ab50$~NFoTg{9EeeZ3HRn!Cm<1&MFt?Y$Xz$'
    '>4g2HSUC@J0x%@iw*VmZB?Oitevu^vL!i&Fh>-~faGfQtdMr^&IDvqo*_euT2h+oF>5$z9|GF8@TDZa-@V-m46us`<S(%qq2l@DB'
    'azO!RTP`=4XEOlUVB=?OsGf{l_gzfLfLRVi;QO2{<ncdt*ZBVdw@V*1%Kdehqh%1KOIKn-Cgnu_#tL)`vOCclatbtsp!0Vd)iunI'
    'h03X&JI{=DrYm0yFxC`r?1=y@bq1=CF(ia{obRYHR0A-6?dZ}4!Rvj7_kKwjk+N;MvAU6)@zoC>%_Us^%c?x{0P#><Vtt;#>t=M$'
    'ZV#%04I?xH%q`M8#)@z?O2Lv0w|i*tSkHv>&+jNnd<SGIvZ1h!&!qYXkLbD0%lwvfQQs-TF^5m{aT$@GIRn_d9Vz8a&*7d`W~q17'
    '=ia2sZyk#aku<^j`i9@)p{-6ftS(s5LMwv|JR`ttwbx~ed65m4#sTs0yVnPrX3!GTCSdp&c>KYx-=m>zxM2OZNoY5MMyTd<db<XW'
    '<W@Nquo&8l7i-e%Bo^)0sr@c^NL~LO^){PWGdaW2ZA;nIjJfO<{&p-?9<0W@(!|2b7FpI^fd_JT7zc(K@1O&VH-$`d%^H+T3d7W1'
    'gM&p4k-o{vULY-F71frez-Y?d2jjdn2!K8=MVZ^g(;{3_BTFxbltuc%Y5R{J^i|;9#m79UoECaG3GKI03k;Porq2u}?VaAN9!$|b'
    'IufrDKH$7PHTASg@6-K(_PUYx=58w>YYrpT2qIh3{i6LRxS_DZCiP%t2RMGhg*na^(^knexOPi{6A4v%#KW@Z@P>jLj{&1dcI7xv'
    '{!XA3t&leL?*%-`w{u|9x6SdiB&%`*P}Q%WQ>y&rC|Nq^+5#bEThBJ$xE80LuU~VTmD%<EsUP#tQ|oUFeBWRo63^~kHNK)76Z~b_'
    'Y-Kqiq+~<7GGk?UWSPAg^rcT|86-0ynz*t{gtMlIbB*SgTQyHRk(`(=Brg0jU~oV}wo^}R5OUBTr4zGUOou`4Z#x9`hpMnVoBpQh'
    '8@gfG<yw3TF8iT*6rYv?DpK(@mSPGuh+0ujpz%?-BWQCIWet9rmt?4o0BNU0w6m0@uj^Zi9DzEX3_*-xnJ~*7;>f)>-271r{)S(4'
    'qjKl}+7YsFv6~ML>)EM~71bB$#`S9r%I?JiyW2LX)SlY40wSdaUz<IMjEpWE=Q3m15)tkuc9Jhb%=(`P$I>Q~!_9d1LTFA%1^bG1'
    '+<S)1X1(s6aDT;5%w{Ep0(nW&)xw%*2gdyInx8>z@c~B0_6Kh3K^e2^cz3>`{R<k6v2?1|_?L^PjD(-k?k$8!63J|~|HzjE(voB9'
    'OK(9rnlwvy>{wB6N!g6(%-+$0%7&`Ej%`mfhizf97Vdx&Fut9v^a~9_nm5V}V=Kp#Yz}*ocSNil&WZnj$?>+!K#qGGo(!-N)jW5T'
    'zuMN`Uf`QZRWtG&h#7%(Z^en}tssVxPo69ZKJ0$4x-l=4Je*8=FTUvl{a&WdO{I8O;|I$Yo0|bW*kL(B_}%Y4!@f@#EwDyct@BuT'
    'UFBfoB2zsk6<As)@tY#I1<&}6C5%%`BY9+M>=qE4;A315p!)noj??0;w!b}EJN8+-CYf7Pr#no9NM_UQRJ#r|$}dRT%IGMVac~cs'
    'wmGa8NsLm`3x)0Cs>%awrzgUvx5oHSNNU3Kgz#XIXC_+(6m?sxLCt#pYy#GinyOg?>-lVEAGa3As^T)zcHj*$Sm)Fj*lURgt-yeT'
    '`M(r;P6CKeN&`%F14F$TM_4^K)V0akGVwIS_E>Lfp*Eo{IDR$BI}_(r1>b*~rif(mwESAwIZ++M-+zD!&!o_p6~6{(3RB$}YYiA`'
    'Z1`PUBA5DgyX-2FEAJbWq#U8nbaN9ua+b8+AkU3I&jeG`%FJR{^?+Ztz)Y`O7QtR4&D9`-Oa&+JpZjql4RxPudC_<rXPY9rR&Ctq'
    '{N+=1HosZHMNbFrcHU`rl*;M5in3wLv@pYZm3}r$a~-AdGvVEgtN0`|tbY$X(0{i8cbN|~+W!MTqcPoSxhy->#2y^FT>VQ~^!#$|'
    't+OsRo{Yva7A}!c4?G5Y;7VQ)yH}){0Qq&!dRyamx)^r{Lu$F%&ZJJq7;zq%8c`tmcOG{ptQ?R^A66nsU4Sd5-^jd)qu-Poji3Eg'
    'TGm^I!H%NUW#Sd~mRX#VcQpUPcwJVh6~#sj?^#B*a1SU@v8WV{c#WSY@8-#nlFKZn)VD!f?r8#9XXSXx7U)bi)GX0!a)g#1G+z%R'
    ')qXt@!qbJx3`?*}me3^kb=OF|9d?}N*R<`1VfiAN%^A^5Lq!47fNBR7KJVeC@a~25H-OG=`GOYE&GF4ohAzXtdI!!dZL;)Me|Pg&'
    'NDZmpO2rux9gRann+Sn6YHXyzf$5plZqXUd!8Z%jfzp)3+nI#h?wfZFqpe_JGBVY18iW;{BhSEsdVSGCAN%X*SRMnrs5SoTuxeAg'
    'h3Fv5fmlNu9}!xyb{uVE>|Hr5>TL(Da+uNNGr-1Ej?Sub$2zNb8wj7xQnA4~^#K&TYqreXFbA8)4Z{9kmu(A&eO;g&{$WFFn`qo='
    'yuw#shxbdO*_jqM+OQbBC2&zIM@YS8@pV7;J*hBN^{U-xjaF8e&<7FVTo6;m0y^42)k+nM21^{Ajuii6AfOyDL^mc4?xwMF>);8Q'
    '-If-UxH@d~Y5;KQPT@+;U8DLlJcL_Tk`U{$qR_p~i88Fhwrd5#BeVZY7+Q>Kl_FfoeaV!0g5S!<OORT!zjwL?*3i1-o5_=A45T9T'
    'D8f7Xr_>Y3RI1_feW}uQj};alh<-aC5Hwv|+A#jf1KYb|fW&-d4I$YPzcU|d)jy^w)l{94{c9ixj)a(rzE3+rL<4ToarBv;;V;%o'
    'lAG>Enegh&$D!TrfjmH_hLj^TqYnm8j{z_Jn_hv&C!J8;yp53O4<Q?2I9rmvBkZjjf<KfX$e=&ZghVZO@eNe{twolml=PoK?ob@c'
    '{LJd(Ek=w76Vjj~aC7O8KRtZ1J%0@Xe*H-f|M=I$O*Eya_O&C-hLHyn@!VWkYXY#N)O+p5`SNCHwU@TLHeK-QPGGX@4j6hShQ6Ck'
    'u7a1lV}IV|Lnr~SPg}rWHG(kJ=tmbe0Xxl>&hxzK9wM}rCw!Ojvj%~<tFDE3TPPU+D`V@Njjri6tq}JP1e=?z8nv;3sKsVn(^6xq'
    'FOAo|>g%h%@1ZNs1w}qsr5eG2@n1+p!stDe(ZCguhW`#ZhS=B}rok!W*)-^OxTWI8V>i*0JgJ&yj9eP7__<Z*V17^Y!HdE%ufX`z'
    'PBv9mK8(R)Rf*}oTmMga_!5FQuU45400QqRy4PaEKtGuqWo++*CYIth=QghB?J4b|SC#F2rZT=-)}xzKe_6S}AdA(h`TZYc>|I~z'
    'cGRD9d<Y2ztKODg!^cMKgMg08R7$c5S=r1kFX&X8ziN=8oA@!T{y}$fZX-hFV@R?-!`R40y;_D<Th`3?n~@Ct3T13QpUM;}z}aV?'
    'pr^M4`z&4@DqxWWhZbGW_L-#;(PyPP!)m)pgjU->;9|VujpfJ#=Te5i&2y2ru88H$6S7`#^8*4KvIbf!`jP6JOe8W1V!3Kj_XGG#'
    'swWTt&RuWKUl+{S#gu+R`ynbf59oPTrE*N@-$QuaIM$V9e&i9Zt;WvL3@K^ARXu`pe)eKiM+o4$a5&(Cip}gd!Ftq-_(N67B@94C'
    'yUA@|vPckDmJ=`eXTGVXd&e1Y*}4*uH_e_~kt8{Un27K^U(78sKU$P>I&tRl$k`h$2X0J>sx+Ig3Djk$YtPw8&WyR&0IScjG8?Uc'
    'S@-5kL<J6=wUEmvoF*KX<U24s^54~V_v}C3=O!no^bh?ljbbF;f~HC%1K_MIy1E_b6}Bq%ZD`psw)%Oeq&S#Qgjy8@=7nY|KU>fm'
    '=o=%aS0-(WZ$H4{oH+N3HI?fcQbkP_{q8`;9K~<bUu@VSzKBA^b6xQ?djmjaKJqwE+ffpqH&~gT&&0>sSj!&0osdx&*EctE#k*Ou'
    'c$>kF!`TG);p=L)vK2?>fJO*81n<9pu)M9rwGIG5N67R?VvL=_2{wO-4^u2a9T+o{8hAXlld}8-$$Z4Vi}O*2#Seu6FivsHbDb1f'
    'M7Y!JTi%VZOb6hGbNoI8u*{k5WXZ2hs5l2zzze}LwwU43Im-m$<%Vp1F8gwT=}yypV~tK|`$*hQImu4p7ONevj}kAFM_%}i=^R3D'
    '(5ujMZ}QfpTQa)G$pzEw(`FUvJ_8vnLCQF{nqf4zQ_Lw5m+5FgtyGpL>suoCZ#_{V{DnC^iVT0x7t6Ke>G{c9W!Rnb#9+xdq^s&z'
    '1x%r-3da9N@2j^%;tSvjQ~yp!F%ZRRy<aJBg{*$loyYt3>bBh^+PQ_)pH7*Q`?kUNO-(zFAAJ!Pf04<s(587JW8#;OaXR?#q=e{?'
    'EIn1UB%xbspwU|~JcS6;Qu4~M8LOWv&nP5I|BYyP&p{7tt1O!#<*x#lJRZw&qFRi<@gPSIEz63avp?$dFib!=0HeAZ0<@{{*nMa;'
    '$HYXrFVZYAe->z_X1j2STr2XQIae4g(r~fJm%LBTOO&U~p=cWD14nOr+Cc)O?jB0G2i^i3r4`--S@>_A4<p@i*g#xr3hQYg9+hg;'
    'tT#imc()Khv0rOwguoLm^-rQ*_Ak_7!1I0ii|Oq)8@|qy%#h(0)c5bvA^lT_UJN)-O9J%a$(HWnM7!9N^EpiP6~vw&bXb^&3H?V='
    'uwx4Z=r}&)aZ0dvn+~Zy^<yT^DqvvIY8NHzQluf^&15^1xlJJI*<C*GSDSu3aF_iWIjN4&p$HXlvvoeq1cseh4OCyrq!b<l499tq'
    'G=s>On;jHo4-TK{J{9)^cYi76py31|mnP1|e<8zZ<E9E5h<n=9!|=`t3aMRTg$q&=i#xa$V<pb7AWIS3>>Q}GyAAxokY)A;G&id@'
    'DZ!+O?M;QU);E2lon8vB#Xj3qah{O+z{(}_mt$nDl*;Z(74`S9V)ohB@IP69rKTw0C|Lf>PY|nsg4N^{o`3WivJG~>2x2MWV&Uc@'
    'bb4kMcI#$h;XF|pZVZwUs?L>Xd0AB5mqJwAofiKri9cA|e5vQz|8kOtTWQOi>yHWOHUJB@lX?5|^>t>1V(Y3~1sc(W!{u8x#e>+V'
    'C1pj5nr?{X1j7KAYrwNC%Q?>MupnJ!IK{@^P~$>E8&RHNyU0Ni&+^Y+l(z%yom?sea`H9^p2o(#BVb&G{n!+h&WdvmoNA@5$ImXi'
    '`?BSL(2ye*b32we=6=#Xw=aqo8);Co{6~++YJPJl-JGY)zZ@!d5I=>KFIu|<BZ*Ex=S(o0!iYg)Ra7{W2K$@3PbEJ!rt<)ob^;GG'
    'C?VKA2q_te2?vSoGesz}1F<?zp-tw_=N_t8A@csqX@G#h*<Fh;KaEZr)|L+3$ecq)zsy9|L!3#QWL_bUz7ctTlO2*50NQJ8B%bVT'
    '1y4s2mxD-6AqT$7J-F)vtjUDSOwH4jF}@R$kA=Q|dMU20)DaSROoe`nFKs2QP1{jC5o!C$@qI7q7QCSRP56jw%$4s$_j&)MA1y@E'
    '-4BIWO{J3fk3BKZ;b_E7ew9{%B1~}WEy%%5gNLv(sg@vuL(rXblC`jGJ%H7CCg3|s`DXK%R|8s1QMueJg=YR&o?s?Bqi8Sru%`Uq'
    'k-*u7e|<M^>Il}XasV1|oP~x9>qg<N=X@IQsg5Pa(tt182`P4EA=yLw)Kz|}G<S#HK2pPwEX}l-fhJ)lL{gR^OF?yMXg*tNr$kvQ'
    '?BY=%3MR0PbgB>K^Y;tN6YjTv)yA|T>d#)?=;#KDA6m%J>`etsfQ7?BGj$}ZrSu_wHjorq?yCWRH5k?DPgZpYN#2{E-bx)KCRqlq'
    '2F7~M#s+Ukv7-e{;j2CC2(U00wg$u&S}QlqZn)aGH(0jyrs(~_Q7gsRX^m^m1*o3BTEcnwX-wd~fD<2@v*`<P*(Llqq34?c%8gJv'
    '*q{zVhQg35H*<&&X#{xsT&IQ8WFDOAbq$iEB?`<T9Kbw-+GM0I4AJSU1pbZq3hT9j+a+^1W;l~8bKK61*GfOOeLU*&*c;CNiedco'
    '8xZXwYm$t0Ppv-4Vfbku>xu8R;S%1g=;Ql-oBzbda>LX)|K$4g5iBjyy)$6FTL{0x)X=OatDn~<M*~SFXe-S8$77ejOSe6KJh-mn'
    'm2$PTTshwuU3^jUvv%-IC-ELF5$C;%p4CjjmrNpqy?#_gC@(~^pstN!*M)}NGTf*nsgPh6jrd8)WDf<e(cE$);LO~0mx~5LM@_dK'
    'txi5XVe+>1H^u1|AN8UTCRzJze`YK+kL1p+&G_=RF0^xkFlQj^i|}5%HIOPlQ~wOKXCVwh=+Yo4F*SJ@!4_1lC42m^=v5YK`}~Z|'
    'FE)1yANuQ~-UiQry!2*nY{YiEw79-2bc48X;}|q|PZ3gCA%(rErURCVe3{dOi84Ok6rCtT_acovgnCjh1|L}gEWDbs$uZ_MDVGxu'
    ')ZI^6pLIfI2v{y8JokZf+<|PyD$31o_T|VvzL$!S<J>V>H0p{i56ku!S2cq^2W(uRaqB#{?lNmK`^;P_P|$x2K-aXqtP}pH9P&h`'
    'ZpB49AH$nnkps<9!?;g`05Vw?A^BA@1zPAW&Vk=jTywRRoXyr8x#EhVW{s!d*IqrPYn%9OYvt1-NhDblFPh8e*mhUikx)Q{K~E9-'
    '&sEta=W{CjjRqW~BtNP|;hnDqag3;5CL$<$&vV_f)L$|;d<_#saFuP7$x+NQigPe5;0ga1<c_qY8#D#sv7$EP6{5hnyVu=`!!b|m'
    '_lqaa$=s+WUvDsUKA#Pr;$1%TlpuhXCT-dTS%KGD%isZj1adr_I(f-5DH&Aya1i1vnv6&J?2dPg*M|906d16?vm(YHYv%bhIoB)V'
    'h<%o-z}_VVLR9<xQwP0uTpe5%UR5cHg3Z(z*pb?edy@)o54w1mYwj(%HXRKu0Quiw_|6&PqWrGVPhKTV(@>0N@pMt*(s1tJEUU=T'
    'KmOP}8(fnnGWwilDRJh<M&WD);gkh?wU<-U&`(E)_vf2c&?B_(D6Dv_bF|~1Z>IZ9sF))w!a*9>=%VqZ2J@k0F*!~PFOkO$X>oFS'
    '|86z_PQG5$NCac=2LKz+O!t#R-+559n8;?i4`Kn}ou0W$-j=Tvz;*RR?p}%{dCs_Y++?yfRPj^G=*Lb(PVnzQ6^XI$S93tpF4P0r'
    '?%;15(220v6k?C^{F{<(QkZm}cW@;=^>9=ODo(A~a{1S=r0(;bKX>8h54~(s_09(-=>U~;hDQ!yfjjmWA%YtFm>vel??{vl(BdD8'
    '08{SffFHV{z{2KD?#Y+Gm@8Kulse$1yaUApkLa20KOh!Ew9$%EVyV{V6QaxPVd;<<<9)5dU4FH2U(^X5YTA_*jhOhKp;_9uCAYi-'
    'GIV_t2Qt^&FBG@hfGYXrsJ4A2@wgk3eXJrCgAak2+Ou3#9HJNUlhNR4!6`5O$*Oo5ne%_FyhYj!M2*hprozvX{OUOnFhF#|eL@f4'
    '+JGjlr_opb=t>$Lpb3TnWKU!)XqxEm(Z%7)#e90fxMox(FId?C$IQK|V&HEoQuT|_*pD?eD#tki7^pk)*PP)E_Flo*bm2LhyzAko'
    'h(09}0vGR(*ffJxe^RCbzFu)F8#O^NHCb^1m3yUqsPAtR*(dYKzwFoch<T}4Ay@#hYX^hYDkK*zrz$<A9R)16Zc6=74Bqy=E^M9b'
    'A0Lo3JKh{MLt@ibQy%g;4E4I+QJ-{C{+<G{a-4cdb+UIC6!4P>2hR-vF@qKP?RaYtE_2<gd(e--(y%Uez?*4$+wt2*v$L7#db7rs'
    'nqwsezrGYQjg9{02Bt3{#+W7**=3-aCt|_atsXT5O4VaU_!<@23#T(*qHUHKOHZGrcMGF!QKbg)QjgxtD$Hd={2``Rcr02XCJjHB'
    'AM1OuMW<v*t$;<3Dh8<&u-Nh#-9B!75QmS`!A|sbZ}v>1*fl29Jk-$Q*FZk7yJ`^eKze~)8dq-WA8h?jK}R1^T>x&dpbeXPG1`I9'
    'Ui7Low(J|1n6}x(oI5ty_1(;EMQd9`$(P&(9hYb8a8`G~uKZ_nz5nwCB^G{z2gyWsy=w7=#X}Un?CUkKBpb`eHx7C)ZyZh$sX7hR'
    '4JtAE;3x}^W`TEX9KNZ-HQ=5KSl@eEWz~P0_6CBK*ls|@>C^Qad7b|IXB(_2iXI(!#F<tT$;L|r1RTF;YME}hbA>)CK6^j7uR$`%'
    'aJ(#kw`4GLSZfIW6FAEv>g+2-6wP4igMsJUy+K61FMWW<87KRYYQgfEP~#F8SV7nCM1D17f!JS-`Ts*2Zx{y56Y(o@m#R12cx{ym'
    ')muN3BZ)u=Br7>UJzy>FfNZm+*%w{C_D+S`WZ}VJR<o{n#3GPUGYi7n4R+Vok%O7KqHh?j-BMB-#kmGQXo)QTkSRpg>|dB-0VSkv'
    'bFl@QF3*xgW-%r~4Xbjl&fzg8V*qeUe)A`-`!|`g6s3`mERQ?DL8%onNGJF-M{OLmg0m9T!1~Hk;b8owVfG?E#Z*r7q*O6%?Xs9d'
    '@?2EkTD!I4OHQ%!CQ~v7z%3@x8Fn~CsxtKEdqg~zgMhRmZlT}q#MhR9uW;9nY$8iJ5y_d8creXnlcr0}@th{2uA8Q^S-fFeK`uv>'
    'x!Xl?n^MFg)>*o+P+_xOH(FLGj(lpzapu>~CtC)`PC5xs?vQ!f!tIVy@JS3J^Uk_7M}Q0=JF^BSjA!^r7~mClO$jc+!gTXFvL^!u'
    '^sYoDb&|28QVRqf#m6gQ2S%E3Nq}pd_*}J!8g~-WWX<1}QL!!3mWrx8`p)W+MqJrscelHou~wWu%9EF_&^Eh|Gv47ppT}h58)80T'
    '8^vHt%gj_XgM#;*COQ(L%$Xn~W;b%e*xCP=|JY+CJ5r9cvbP|BF@)Sj^vJ^YGuEMMAUe%S-ZW9qD0hmiiK3l~^gxM|NL#5oSm<Hn'
    'aSO^XuqClDZJr2m)b-2%x~iI{yzr63;ogOIPc^@7#=W(Hg+w5X1^wV#>4}p}0%5E2yPd^;ARD)DJF}6?D8N410SVvshQV)#xZ{ci'
    'PlB<^a?;D64G0)3*1>s+-O7LI4X7`qJ)3nVNeSZD9A?RzX3SfQ@#m|&(7-U|Peu9ScjZd>1O8#`1b0Wxw+!DJHyIag<|~XcjYF+e'
    'v3}6{wodfktxQM|(7~oZFr^f;9V>vMUKK8K`!OCWgdK$WYrA0c;RC%CVkT_|JQsGlP!syv5||MhU8FL(AhP?eaysDDr(LkSLrVB9'
    '7QnG&4wSmL*Q{mlr!B2NQ2rG<e0c808EkPFn5f!8o4!5*`USJfZ+(U+OQS~*%e8JPOAJ<Vie~|SE1_o?CWVSM+RK-^J}TUsMul{M'
    '@L9R`M1IT$*WY3Rk$LUU<*q{JK;6Z^1Z+v)49|K7l^(N41F0PSj;je#Vv@!Bqq}&_Xq9a5hYL(T@b8D^N`EDp<0n;7n)@$&jqb~c'
    '^0;T(74~{+fMkmoFU3i$&C#ZUTw3(Jc^iEPe6;*wTg}}Njwa};HQe>qATXEM=wgR68Y^#2|0?In*N+~51o97B!!Z)&+?;J`O=8Iv'
    'uM$+?aaRZ;cO)K;Jzhr#e6v7I3t!GNRb!I$ztF1?fft7Zw--Qm={y*Zks~oui%^8bBS^7u0?Zt3;-wThko0_wWVd5+bT>8KoSD$}'
    'ex53_GJ`mph%sTuO!c>FZ*oBqvw}lSALfmFaR9YEj$}~_B|K*1xATkdcll5KZ|f(;8uGc|RKx}csQ{eu6^_w8r$vuxqfe=XD+`j<'
    'W|Z|L1JxAIGDSbAXy-<9O6{R841tm%cVWhmuyZ&{t~TxmErcx<Y=9IrAW<t6Rx>zPb#eg{AX~{APuMGwS8nw>??}0LDL=xiR~4uo'
    'H2sV>#_Q87*9fMlBnMPsmcBN81v<*JJQ=r}Qu?>KP`9?bxK|X|EKy5BCMW|)-S4DPp1i=G@@*H9MpvVD=7XZj21dFE{oaColAnK('
    '@fSIL;{H2A0vhH1jeJmEm&oAgtKyis_ZetYQia_Cm!IR|$vVG)quWqnZqURrpi)abprv)<`g{V#31zkumr;Wd>dT9KH;`2P)3E+z'
    'b83@01&p<)Rw1>OLRJN`zvkcm{rS}LDpk#M=I(_KOQkL;`fz55!zYypAk#@vQEUT%x4jtWEwnMh8EnzmkRkZ$rd?$Xm`bdk;H5^a'
    'Qcu}caVyWD3lN(Uv95#ndJ-xTb)}$46ofduL~B(unZiON7@EE7gNfOXy@LyIZamE!4pCcvJqV9o1~P`DCVXANHCdU~tU2}Z8`jDL'
    '+iy{mI!9G<BR*&j=M86Ft%@Fw*_KKY{!Ul<qUxrmQdRYIoA^5F%4)NiMBG7I3XS~H?9N&lgasN#H6_uWe7C)PsKb$pk2&rE71~t('
    '?msuDM7V~|mX`mqU2`Icsl@co(}VyTtg&9%y<s7~BpBShYleKKVa%c6`X#^ixWDREOSHZ8D~(j43yRa}u~gJvqHpKn*LuU=8v+xS'
    'c)Zp<3^>ZB<HE@(EVv5f?o<x@T4+RNj7L892W}-MD-=UTYH-{i>gmb-JzJN7t`Ju*Q$3#Gi4LwtFL&*}&ZervLIlt1v}6EDg)$`+'
    '8Qc=O9fHHV{Z3lia;SXgBEnS>PDZ^^uCS4(%KP)#F3LUPuC5GO&WcQ8bd~j#$`YsB>bu+{RZhpVn{i!gI(IN;T>}%Y#Kz;eCA(Pb'
    'dmPh2RGT~1`0=K@?vyet?02|@hGE?83vUgo`ve_jBgXV0kF*w<q|n)z%l6)93lQexl2(loRT1B8R3_ip7WpBNT}Q^p;_-ov_$+`)'
    'T>VsK!Tn44<@<kre=_1atGM!!-|4JKFMn_sa-<(JpI&?IB$pIZhBue!bgDz46nG6fjAM#ZN3pd~YAa&t>^q4KjvMKw;?05>Hn~Mr'
    '!LE<U>HUfG;x_YH2u4J`v`>2#Hq!DJg(0&~<bEMStnQ7i{cF6~k-d3gR$-E-NkmG<3smBtA!<Bv4Jk^>bNcPq*5hL;7~sX7C^Iwk'
    'lTF%RS32xtNErkjC^ksHTVRJ7g5u?}lK0VlXK5^u0N0RZe?l#nqVJD}*cGQhPq<d!3Qz)VDYNsQrOhUOcY}ySFE$pLt1O=>E-*EB'
    'AlQY-eN;QH>^1nt+w&T8WX5K4%(;63;f2gMRb|4fn&?Tzm$>11R^!qI2r=EsGdp*VtnL}5C!7sSOTr)>`MD^-ma{<T2lf@RQI42>'
    'DN~}nMaOUY3-AnXzQ>{5)8}6@S1yA>IC-~kD}>^slND@Q!OUuS_j62zpi|?2yAbt6hq02yi|LML;HP}A?!H2OP33@*wKHhc#OoQc'
    'TyF){700N|X<n&p_~qD`X7`v?>|ED%n%?F*3GJY3JGKU63bKnZWl4&Z+M;6GLx*t9V6F_*I{2W~7OJU_Ov#Ap6q!cn;pA1xVn4&K'
    'm{qwyRbK$Rh?=BHQ+>RVtl|!pl_Wt2_oS~~D!l?3rD{o8*qZBp@iQvN|BKyvJbdnx7r%zD9%eZ*ivOeXU%<GilG<if<@X_814X+s'
    '5S`6+rT=@V+t#a`JCirS@lNi-S(Q`Iq0|CwJ(xSas5fK>rj%N+P^dT^DlNPF_#rvJ82XL6#FdJPi4UkDofUx-49ihkLeoZ(o*Jh~'
    'F|j*_BHigPc1q~9>VYBLMaE8*p)(~?A)Soq8Gm68UM^XC^2ObJKhGB9P&b0neU-<;CyouO(x&U=2XG69&vI`XWWJOxcy|-P1@6S='
    'Gr$ifPFF3ek8uz>!vu4(veR5Phwo2HM$c3$%k&aSu<r8y<93?Pj;P{r*O$BHBVSMR2Svgqo;1?6<e2?*jfw*|bKTz;#AoLzk2WxR'
    '=c@75rnv7Ru;1ECbcM?NfaqKFf+6~xFJTk&@fQt`w?~`~?}DX1$pl;=p_fFh_=22g^7xJ<mzl8h+ptncO2n}$EU6%<9g^{;UBTFG'
    'ASJ3PC=GFgETo!6dX}O$WX~85T7sy-CZ1UsA>)(E4`~PLBj98qvq8;Mc?$d9&8RnP82)>HaxEE-k+`#xRMflqj91FsF^vPH*5E?t'
    'dlo3J)D=&G)n28|Et!p!xG_zPRXY9-yoKQDI@f8ZZ43!weaR*JKQE`m9J<v*FHWVzCgzXlP#c*T&N15Qte;&!3KR<;zkqcmQvx2s'
    'b{~3;)3%I~U=WyQ68r#IAq&`1%LvZ|w-|nGV|6RKn|3r8f3}q$&uWkU3xx>v-dh3WAyk4B=~V)ZsneIcDgQMOj!K>W;*UsC60MCh'
    'VzY63Cc(2U+|rRE5Dg%+DVdRst~9K)jT@3p>!^{atB>(RjpJ_UBA@-x7`|DS+54Pc&JcJ6b&vdiQ)q^ZYIoT}!s>ECq4{-}<d3cw'
    '{m1v$WY)9yRDp2+R@h@oA~mN&#$lOmlRN}hoB=&{LD@V~u;p2$)h1^98h$o{nr+WOEHOj!k&=Z^s{mptK%EvmJkHd!J1o8BLk<e^'
    '^NCu$nuh+YA>FPGFX<uxOkQq<+Ppr03WabFvMSk3BpYuhI(S30*_+2hhTFY;8hVccDTCKN0-nPxjP3YLF%oq9&-l@SPV~q42|7N|'
    'f_A;Mb&)j31yY9Sku(>0jasUA?s;4gw<Rr3^bm_bjGM2H=g655vdl2iK2rFpP;xStuylR3plB}wtdaU&nMx5BX+5@n{M%?THC`(g'
    'jy3hUHF=L)6Xls$#8cCsIRQ|L_jHT?_{#G1p-h1d-o)210CCk&osh1MTra8#dD)>==-h#}S`{Ig8#4<mn}o;U-`TUhd3qglbpAh>'
    'ywMOv`4F>TRa(kM8|FldQ3mB@owSU3613EIt%Vs{Xi|SR)}0;IF5n~%yq7MmHl`~D`V;Rg{MSM`*UI#(SWi#zKTw9<N(erC#J^*K'
    'Pz|0djiVxFHQ>Jt8-EvTq&&l)*9RXB$rVqHmv>%L1ZDC{R2BMDG6Y~$6|aMMA&XZ~EE#XRP7uKMnDAl6l}_>(u8cQ;xf)t)Sf%YW'
    'Id~1GH@jBjr--UG=F9in)x;|f1=iG6oDbzB48<uGePMT_0|Pf|j>Za34XGIw5uSL4=;z4v;(p7G0M?6(?vsWPo*TND?4uHV)TED3'
    '%^b!&a~!4DduKN0xUa8x%cl4~6MH4PE*}!i0bIxsJI<{fIcy3>xa2g89j|CIE^Ie>?fEa0XvvKMtVN2XSq$=n_b*h+4&{L4;Zs=m'
    'h_JbbR6igjTv0(~aPx2~pZ{EO4I1<YD((Y~8ileNe?8k<?}yI`<DQ4_8@T;wQ8hHTqk$?g^G6$e6~pU5(BB=#xx#Et8;yuW#X9})'
    '!YXsZD(47EN*rc3K;pc1KioinB&|9cVyJuO+&17em}fs;BlQXNs*rt2GCzAb`}5Nu0FRf6^q0L`eRjNi(}mC^#fOMsa(X=Ljws#d'
    'wVw<wgV)wnOp*)%D0d`h;52(v9$1n@MrGh}WrqL2G$Qnq`2gc7<0w$I?X~oVgRYOmW>S-_S~24D3Vm?hJ=(BM6DBKlE8wbyr>X=('
    'c5h=-E=3RTCm!T%Gr;{^5K!}Iq)Kx#s#^zYj?bW(pJXn=?*y_7c2`6rSq5tDN)AP3)C{j^Crfb!m1dAu>Ukmy5nC!f)DCE2u6dzR'
    '!~oz9*$|=UW(g{4k!=+)Ixk3O%IOpXD9U24h~QN+oct7P{{tMB&Xi;Zw2-)@WZQ+nIoXTp&4sbFm%^mqS7!iqJwsH=%6jOXpFCjW'
    'mlTWH`RxA~{#>B$Kt1n*HRrNMvJmk;tr-j~AWykB()8=Bq=@{zxh}jllR8H7jO{u={bpX#kEyn!c0ySh9lFnn^8u9py4w2(ER1$K'
    'NC@g$QZ2}2nKtujalo;~%zrtWSIFLK^S$DMMe&B<k%Z?8Bn3R5XI>+*yxwk4x(SIO42I40sPNK-q9d1y$*jY!)f1Ii077e7*h3SQ'
    'qj&P$Wunw|2v8(09ocbi^wUD>-uZVwjIO}<m?ajD+(`z{iiUO6b$=p#t9(qS(jYg`^Qrg>7?vOtIhrLv3D<6J<tCh&(w3mG&_tsf'
    'yMQp_maZe5MAS%zR-}RO$VrZvlI`z>zE9TJ^GD87USO10HmNKB$j<5e3o`W0E|hU@YuEz52^9m2uHF-)Ir=Z`TuwJ~DwaE)51&BQ'
    '9D?Hg(?b+@ipz$c_L8(J)>ANk1iPSlUmr$);&8DhxO4ymrV1^nV1$BuBiequ60L+iIkU+oc1F{&p#PMNg*-FIa^6<y9HYiM1+l0O'
    'L?%|qCR^^u^AodkvXIAQ>beboRS8CvW_)M6DPeB>pWmwidNp3IgO4)dE=h=>IX{@_9g8h6qIrkW1V`V`Y?s(5$|}$~<;sURYL*l{'
    'd4?j!fj3fN!kOZS22(}og$t@F)=MP%@2Erm+p698u_n}@_;%Q9;S@AH%7F{wXWRl_i0F?}6<$i_thgp;@-g7;2G9VVyd+#@2|bHR'
    '+v))hej97-F~~8N);S$%4C)mH8?8{RT4mRO?J=oy65<nHLnO17a1&qI&!PphtgxajOtjD{W3%R|;z9>b2UR4q)Kj5sCcUW{wA)?Q'
    '@xsbno;0A`W9FhbJ?qHKn=89XKVr~L+@dVsy77>K^g==E;;DS!0{p5jhkCplQpS8cQo?tUHh-fngp%B;Ane>g-2y7twD57kV=2LH'
    'atN(Xxw5E!P1KOjx?FVy!Y;~EDoS$Z=!9z|qergDM10{DX`=Z;E)4D_41x8O48`FC*Gls55gA0Lb8*nS??_oFhBakEEpP;2HAy;c'
    'hvd18oAM8bUU@R2?&bcjh7t=h2c&Kaoo7|>%-??#k3Zi>1y%#d3JxIJ_a8EIS2#pJq~zs7VDxfLHb(_!-owfYHJfk>?k^RE*_n1u'
    '%oE$jB(nwwm9UpSR!#$5^xT!`R=Nnw_vFFZ^ph4V_388hGAoI2-P&$XO~rwzTJM|&$YH+9Q++wIf-ec3tZ0mBZk9|uZwLPc*1p}g'
    '<Z!{Zfd2Ktk7!`V*iA*pd$3M>&<9Uq5S&tX-NMGTlYh++daL=+-#ZcIyS5m5PI5|ln22Uj$MsBFHTl-7ZoK9{t@%CwaMS$Rf@Q5m'
    'u_r*P`g5hFS}ni6R?9jBbkn_Th;R2^Qj!Yg{TihuS8#f%K3L}wtvZq(4GqEAJ&cKJ;2Sp!4Fc-iWxKcTx_^~8(H#qNPgARNo6Yb='
    'OhJ&5En((&I>@-qd{Ythwm#j9Ogy!~imda=d6`<of1yn>TYJP?FAV547&=d&l4iTeO^vedXyMjq4E2!j^+#5425p}*#~jh?n`w=$'
    'X?QG21#4=1)iA4aw=6*~MgFo#`4bgC%H75~_qkd2uoCtolG`e#mu++kI!t}EiUg<;!Jkiyp6%3AC8EX$6ix<Qd(V5?Ky?ofn}lL#'
    'lSIo;g{l1ci4QPinSqYqW^un}OS>4DHCc=*OQz2;!if`qFUJ6kyKeu*P!`L>mGnj!#kaVWZ8V^X@j+1{8X3DtKsik#s+y;7qME0H'
    'whv)BRN>-qaK44uZ6%~nwO?yg+?U1O$Am(tYOG4OD2ZZhk%rSmIDJoH<`d=7_*b#KCtrkK@olU0vrv9%oA!Er_$rUJ9>kxVi-2mP'
    'V^S>-AdiE0H^rG{GHO=_)qJszklGtSV4B}iy2CPSDmZ@A1{*_IS*7w+fBKg00l<}PJqs~i(m6L{qloz(490*xt3_SupFj|DE;+AL'
    'z-%9E1EVLK-89&wTYtoz|IGPhCSe}!5*~YLZbDAiHm@)Oas=DLP&t=eTTCT3dN)1sZ9jeYxy{3AVc4AEe?Ejuu8GhiK*o2ilc~IA'
    'F|}@_I+9p9Ec%%R$T}(JQod(xkkc(Ha)+8=xL2KM-i+>d_I19oNZvHtD<!>uE9mDBOiHU|Ow0KAeMdZA_eWddW!winF$tUj;Zb<k'
    'T6aixQ|QS{SJjuXVn+q6Bmg)5S1v<f5$BtCCPQJ5?i`JQ*8e*dU4(_MU_lxVlSMp}x2^$c5^okPCWGQgWb(9bfCXwro#ot2x}0RL'
    'j#5}T7X0r{O>{2rFJB2F^ido$%9&n^m<!^p05OSx;EB1G#{sUy14O8itV{~b>$Juu^jS293E7WXY9t4Px@SI1jm|sm@vA;7r5*;4'
    'J#UxSmQKpzAom!8x{K0D=ywuEr;3(vH@;<8nQh+-C%akBV<0P?mjQLuA-qI&Q1*S;VORZz<#B5FbOTL;Byt+GVM8uvp$grvzu`0!'
    '70bOj^i#eRxoE!r*f=M~2iGTNS{=};m{oC<Plv07+9-|j5>9=Tp|QLo5e_siyEnaj;ir8-lvUo1ZjQ|bjOkxIt^xsVnw2jIS{W)Z'
    '8@^AJFTUY$5WStjbpier(LsL>?H2Cg1=6CT96uLPjUWcp3TM>$-9Zv3+phuZP%dncQ`fz){(K|f9Gwxr0LWg$V5x3twe`CiB7!*8'
    'nDBtF%c%DK_f@J7d1*zr3xG<pNtrGX0gRSUe6anG#IBvy$ae1cb>Uan3>ff{Y`NXMQ&T070-r9R`&5mR*JN;KV@dF8_w)ZN2{#R>'
    '@IAt%Q_baL10}$3lkrgAm-BG$xh75YoBKgiM{o_jAS<cpxmT)zhM{^Q9D=_e6LXd+9U7Qs3M}P(;@!LGXklHO(KOv7tJ+YD;hEJ6'
    '*toKD;|R^>1<nuvo!JI8f9&i1YDa_VZw`VY<QwdT8CgD$muiqxa%pe73n#j!$mfohO5{eFiuH6nT={to!0e8)k*wMw+#{+mF;F*M'
    'R7YP-sZ*b6^@(FV*Co!uArXc;mny!fwd5i@j1jU+mod5fY^HAFh5Rhpsz&Eu*JLLfgr*;vk0qu{gV;R`T^@j30e2NeL!{a5z|F5T'
    'c)P&mRmQ<#Eyx{@#Qr>Lgh%oiElvG?b9!~MBz1z^pXiC3|KNpEbXnM2*;mxE&Ct9Ph)WS%@V+v4`x5x0{a_rp`cd&I1nkXxf&w}e'
    'oQ0DWj{D}sRuZjOR^()n@fxpVga~+rA%GSi56qXSdQ{cW@%=d7`)c`=!vWqQ#@Z}_1x`%u=9Fv06L1aoX|32*;~hjPr@tJm<t{e#'
    'rV58dzgJ?prMVQd<1ZWKi|M(KfTP455!6^jv{@mCx;584&g1LD)>%{(3vckIG2Jbc`AG=-0ycw3JHK+?;3TMX@bgcZ#IJTwUrrEs'
    'b$_H}e<i_JwMP<Z$0}_-MtrE46H)zn02KfT{O^Km;A)W0))bP)6ntQ-b@M;YA<E#GHy~q;@Pg?KXz&8KCCI;ktdCXV$eoEBeVxt3'
    'RkQwn`5F_##d5zjB*TL#Lwh}0N9YeOTcwlw_cu7ow42ZETOpkD2yR&|&LT<f6iq0h>zR>an!aT@Bo!$Gic55$JYF`zm~M37T>s3y'
    'O#xw;@Y=nXe(C!4+>^PL6xzwar9Iapu~Kw-RaQ61Ezf<Isw7cyKBIh~@ovNH8Z0SZV`4Cple4k>>@lk3fvrx4^ei}awR8P&GxNQl'
    '_SOpxUm+z=n$u7Pm<%UyQ1b|3H8NOxk4f8B8QV|Jz!8T=(K_ewAT@&7>#>MXy7QRjqNBj*j)Bn$YY?5q%=irT_L2mnkDNw9fYRV{'
    ';d6<>h2>RW-k1BVgyBeK=ZzI=aP4ivoFfci*wDn82|I?=2goy@dvW1|)eL%w!ejeyLWz;a(n_m(6CXv;VZ%abb2n2laUlS=8m@>?'
    'I?@0f!@~`_rP;4KJwB^%GIW$JOedX^SIy%+gr7v~C9yx&LER*s0WmZuV>)`PjyW|d<ohA}geQ7Vo&CNe6ng)T+?#Zb4)hrBy9f30'
    'ID4%_KH!SY*CAgrpM$?+C)pH+$B%*1tqF#E?!zGOX_~_tQQOFK)x@=e?RD6LwW7ZzI=`tcj(xcFT{5>`h&DF$$GY=6(G?4B!NU8Y'
    'WO^_+ww;V0Q>*M<fEd|*rD&8_%1~N%x@Otm3M#HJ;JQzmG=MX-L?`YmzIBPl_k>7cWkf2lbfL6r1hS=|MAQN^OC;_J9PX2<JOMiJ'
    'BHtvYte`9G7L4~6V0uo1zPv?@SUuyAqG!*jo>jO^PR72k!R3h2tODdcW`y1sfLsaoHt55Nf<<}>6!n#bJs7J_t;lyUT#TEcxGz<t'
    'CG27vY!&XUnUbr8#*db@t3u@paLgL#6s})ElN(OBy@)_XTT$GG-BNuksO{`^Z*I9{OuHulZ7v!}CP8R2{lN|ROm1Sr_g+i^A8#S2'
    '=9Oe9!M_2wPn^LGu(CrkG54bBA=Uc^LH9tSft5hhf6=|5uNSYL^{4E|62qse#^M%wNe5W$(IMMlrpq=hEPf+JC=o{poG+1X8Z%~='
    '9d_bAAKX$}ZUG2N@ow8lrffQ76z=ER4Ez~;3*%@$VPD-F>p&J53qw)m^J?_nKeE6}zJ~HW=wzr-&lsA&?-DaveNKZsN8U1S203JS'
    '1q42BRM@Ul)zrGUxax|+T>`@&?ND;6^Bn8Oyfz7R!A5rIxi@zuTdzf@S9@;G5|(v45*;R6JkQNzc>`&mCZz&3rsK8T)gDx<Kf-}='
    'VytUdq%(`mFOcR`zKj7ob+S|sO+-@+=d8VR5n>(8eX2$el93}xXhLYjAx||23W$>XbB5O{Kd|}5*rHt7qp&W;Ne3(~qQj^rvph{0'
    'nH@~^DmT9BoOpHqg}SHKy!ljQC-5=IFWCQ!>N-5|VM|bO3{~fz+czvEY{<&~_Ts$MEOn}uHX-#XBrA$D@BE?wOyJrdDmni&#8Z(W'
    'QvMT7HeP<@Y3@g~9kRy1|2#WGrE-aqJX^KSdabAx7gx4ws$*z<s?wN2w6qA%nra9x&n_Zca=2ZL@ExUqfd5fQlqUJ%>P*HbLTkj|'
    'hi3?DlIX<5`{SFx>AsWg-RBxQp{}^-?sw1Ux72dPXhu>uW*j@p;LtF5@>ZMvpRn;tWTSg1^#uV#r^ZiKHf}}eHc|q+LsXSwJ*@0A'
    'd4QM`63GL97JW=e{IJyb0zgl&5<ljM>_!fCs~z%}cp4|x)bjmrIA&<OT-6rH29{pbMyJ0&V^I`>*J;LlZR!~6JhQUk@iM`|3Lg+$'
    '<e>1ypdeGrsk4fkxS&_5ysAZ1xz>JAU7^1E6Z`hb&R|-Gz4zph`<Y0sPp)`xpSo^vKyu|k!(J9dRD+Ig+sr5WsI^Lo-{>@$*vQZ+'
    '-{s1A_w*L=`46+z`{KSCH@J~gA(tkxw;pno6;`5uNV=QiRRbMMy=Y-<Jz&#_b-kq%&M>c<<WpHo6eUc<;Pw@|@^h(_KOl%3B1Sa?'
    'opl$4T6sI;pkLvOvUq;8Y=KwcXeG%D=-*6_o0Xp@MgEhZUbTA`<#c~!Th%BvPLDokA%Y%Xwj7!5gHb$)-jRIZkBzYHsqF~k$H{B$'
    '=$k$W2h>t(7``>|ml#W9sH}ZrqU394cGlVTzZNSbEPMfZ&Q(x``T#oAic1xsZHY;1rQF;D93bk#M_5ds{k8gSUs=i>#GEty0Mm<{'
    '$;B>z6->2A7COEM#^*?wu`q$~=U75$kA>}nhIs(|XirOo>bO(7VsbSA^a(Iv9N_(exDAGV9Rk^L8RBI^_a9G6uRwovVmv4m5ww6X'
    'v`;g~Cq>S5`A&)Zfc8$z=+;W&EyGf@AiB1l<r?M&+A`F}KZ*Y!vW+1Dw-&=&vmF&?@XrDP*N}7cE=~;UFVqdd<M4<S%nTktQ_?Wz'
    'M>u!^14UEwu5g`dv&;A8)fHS>get^BOUX}EjI9o8rImotsP>1QBc^m>+uS&ij!dN4h>j6CFTrrjFNom?bfH<_N`EYbpU<==1TL62'
    '&@_kGFpMzKoN1<?0h%=hR6hsHi_<KzR`QZ68t$`~+`-$?mA<7`<H6Bx4>>{k;W7<4?yJbO{y)}PGo^vwD1Z~_u|vQeDtz@TnHJ-)'
    'ehl5Pz=ZWI)`^a&w`1+KHBi>|=i1m3;)Ba;^1gR0Pl<AAc3vLHg?dr@@Iz5eh7;l&JgkZz?u;!_iV$zdToW;p(qjg0dZ#jdxT`cj'
    'k<GH){-xr6&wb7JCotL*%4IDQCrv~!tk+@hJ9RV4E*)m!*dj^7Js$BC<64U^z?!+OA#7xzp0(s{V1)t+NHg6yb$LJV);;bu?0c*W'
    '3gGR$I?vl|C&=C-s94~9liVq~2vunC`P$k9=~Kv=Fy;TOWbA)RKW9)PkMW>u_>M{0$tMfNc4LyDhzS-FP%~Y*?b&k^0^6bZpypr#'
    '%hSCCU29ng9D2q5<OZ_e7QWk1wERB4<rw%ypBB2hr~^<fK%#bj*;w)dd}d@0BLq;oT3Xb@|Cw{IhNg$})_n`&Il|Ymv+AHmqwWX+'
    '`4Ycv4Ls<-BxXaR)4LbbX1k#ONkhc0uZ=+FH-O})`angPLf5RX;=IAg4!-oUQME?>!`H99EF9IGt*JW_;rh#op*nhOF$fUG5OERC'
    'Fw8IZ*MUBM`g(u@1|&U3+P!EA^}-zBi`Ko!5JAWGMUyL*&Y5Bw3UD?QQw*O5jvkMb5udjv;C7~@78>L{kTt_6SRyr<`HMp_)4mGd'
    'kNy%AmjCqS6{q@HTds`suOpyOhSj29UiC@=Vjbz9j;Z~6=(+!-VdC-?w=I@E*fe}yT2EPwx1Iv>4ID0x3O${&zcKN{>Ad1_C=r#C'
    'aPidl)&{RRer~u8l>_2uYp!ZEau#7%U<yFRb8wYSTN0O)B;9|uY^8B(KT`}|uo8lWo=~$-Wzx@l_Z|PTDl$=s!EakLDNN2pg~9&E'
    'CfSE#02GVtx<;PT6PKjh_KR!J=CL2U9&1X)8J9xEtYE<MK}j^cv6Vd(8Q#S5003@R9~+u7$sIMLj9>Dnu$=Ex8#1AQ6uj#L1~p>z'
    '8&bwO6@s_daHNUf=@)u9L3`;tEXkhwX_u!QpD~McSqRlN@2j3_ehLtr#-2d#SV=5fDK-c=<eMy6n;{#-K!t>i^PDAwrOf&CF6hZE'
    'ox5b-7^%}}ipP<^&|w#MKR$@84f2E~sAANl#fEQ0bYIEAyA0}b2hPTJ9ir1*{eWMxPh{7yg1zY-FpxBMID&$^5AVB~dcG-LJ!C!('
    '&kq^De)~Je!5pR1&NzU9z9n%HB>TRx2(v@~q7B5kq*&mT4gL43mGdZVld9Jf&>mEy2`qLr=&h@redHtQO^qQ^aEljdf9&sHC=s@v'
    '5|0G_80yc2(4lV)BT`NIe%1oh@mU3`j2;loL{4x~<u7!&>iweWFi?U7fa|b%mBe}4)=-r|pZ^x*YXCqTK8}Z~a>g3T9!`Azev&sI'
    'x;M_hfRbc#;S}I&vCEbmvh{j)p}O-EmSDFh`+gdyKf-cJXA&H&&31;=%xRApa>X?ED~-}jN61q^8vma1m<x6iKuERtY=a>MqQI9D'
    'f@b5MgAl0*PQK!3#t?Q{r7ZSeFaiGUBjoMKVhCPqG1##+GP^lA*?ZyTj!ZhL{PU?kmphqr=YSl3_;}=GtXnQrd68j?Uel?zmv3q^'
    'Ki3X}SkwoJeOT(Q5K^s0JO~!51VzNJNYRq8p;xO4?0A25)f`XjfPnsaqXvGMc4lxNhhS!|iG@=eYFkvsUX~Ug?1bgUs=v>{gO3Nf'
    '&1CVz;fY*0CdI-WZQNygAb(vDMQp)$fQ`>uoy+WD>-N1eH>rA+!EZ(+Cu^ZsjQSM$-zW39w;XCVVgl~3I@$zdPv&sEzg*}M%$lED'
    ')E?QmB$L#(RcgmatQAp^0b*}GdQJZ4mYi`r<r`mlV}Y?^u9tR0c>O(;Ker(Ihjh}pf6aH&d21puV)Y)uRWecH?4e^DJd(iffBD9H'
    'NfnB=|1FAenej=h2ih-O>>JF)qrn3EfLtJheig2eF6vt`$$`Ix-vOa8&PP!!1LiH+ua!T1nYW^<70pp0WS!*SV>*hlq~dR1;_JaQ'
    ';uu{N#-j4@<NN71NJ+rFh&LKB4__TQ+%f!CU!0>s2%Vbs4vP5JL)Cc2>z3&2(FXQ8%Bjr2@zti9W8&5Bgi9H~jTBj1%UXCGR1~12'
    'SLKPPZGq7TB=0lSXy#I3N7A0{prJY-J4xdKs|^vj_jS5)I$b+d;bBXHDgW9EpY=Nj$DD4)do<tiVDNWZ%h(nVBQI8(ROV9G?tQhM'
    'mF2`BOZ~{E#3kFlLsT6#JKPBz5pM!aod?A-kur4s2?oB~Z#$C=9oa!Jv2_WH(-(^-cFz__2aBHsh^f2rz+Q>j0ZWAC$@tXn&48LP'
    '>X5eatgRg}gv$UA*f%?lsnU#BJ!S^^VA#XMUf#uB@zWh1<pcK-of{0WqueDQWCBTDMAY|zYfM3H*vYdu|5n9e!7^d4y`V`o$@kcb'
    'EHk0huYe0S+ai<67a>KCR)7L}a5Ur@u`2=+!O~Pv#dkR^X8#H<SkM_2Y2c;YGycA8|J@1v3#aORg4sbS=pwf<CqYqd?oQ7pLPdkp'
    '1!t8V0#H*k=4mua$4MLuMYftD5mnoD(@$3kI*<y-#`G@lQ#->=?e}jHh!BCgM-9Q~#5`;xd*|ATZ(l!H00ae_;#gEQ@G(FVqUU0X'
    '7gqcVqA*bn5*v4)%%js0qXY;QX=*qJh9nx0D~hxU(FtIo^q{WsN1M`-xp$_XX{&7TUpsS)Og_gRM*&Hyxs^tdM3$Dj{gFCHo)NLz'
    '7E7bUNNzn_nwot@q}M)HS!JJV_B5l)F?NMhtigW3qZ^04v6c~sRH-&^zrUzXPz2pNo+K&>hA!)}#rP0Bp%^6hNVapDC5DlrXx{qg'
    '*sJLRT=U~`SC<m47YBd<k0)H{<OSgl$;ES$A}Vat-l$)!i%1{j70fSU;aKiG>jmUnD8qG7!(6XM-XV<h0tOXtgse}kQbBmdPf=~J'
    'R_=%WBC!&^s^h;9?-uoVGF-6(U4`gC+aPvTkvG<xdh~{hy6WIz?)^YO94~QJw!;9%24gDtf|QVBoLj`adhpzO2o-4~4#uZmxcQ8X'
    'Qti4)?ypJA6T?Td(IDmoHhR=J4!c!3MG|kh;sO=17T;w*-cT<8g@`rc$&Ya7s{`{7N~>gbl&y4tV)>&B!)m_Eq51OwJ%Aqo1!u#A'
    ')yyesJOF<aEhhn%QzUfgf(ZW$h&w3Vu}z-xrUb{F2eNYW|8rSZCwY@x#aiEscwko!t2}h{3Vp?!?Vv}CPcAh!8QZW*3mtyAXPgCG'
    '4XQu40_UJ$<uJR}U2&mo^#X&3K|)n1-bFD6Ymk?UcbRU8ddO3LJ)Lkw+4|v|@einYrRv;Ht&5_$=N-;hbETVe4PdCfbxsB9q6B4R'
    'CYnQi051mL3NUcP5eCB?R9H^1OrC^L)l2$n8l3Yds*KZ&DRS4WZh<y=;j`JQ|A~fze#VJS1Gxuf`i(Ef&sul^3^gVosaS>ip7dwd'
    '%~Fz2Y`}Un0Ha?!P3YaV?j?c+h6-dU64~&|o1#~hhW6q}&<lvpb-p(IbxR{8br06T0I@V%5#@ziP-1epTG;L+XUNe|ko{_FrzeLt'
    '%6|x)F7(t$;fZfhn>Sf<ELtGpY3W5sZxPvH7)nWH_*jSu$X;=8t?V(ibi}6sc^!esGJ7gYK~ggJnL%TFfp(U6jw#11R2i#jF$|_0'
    'Z-PVxv)8<NOPcM1Ky4IS4C0~ORi~!j#QZ?S`$tMTek0HWgG4!hxs<6vEbyNr8a(pm-ez<RNxlPiL^y;*=Gd&XFVqM80}?(~I;>Bi'
    'a!-M_J6Snwk(0cuL1Aceb2C^$S5XY4ej3mc7NHv?KPTkCzhi8r$)9xm5I33_p!gEZ;Gb{$H6zf0!6BqN#wvLB(F~KpxGr<T1&CmW'
    'tMNvl2pjpLYs{3JB@w3)8{xgxjl!(`;HD+|C8mHbm>`mQ;5jBSzB0yqjqHk?*mfqy&DSqCZZW0!Om2rWI+M29HFcCUTPm4c(LdU0'
    'V0G#BxZ%YBdlst>uOZq<nA>?U@{zD>3!@mAMt*3NFD*SV3s#~IHF!_wzcG?6Z&j$exZ#8*GndlZwC4s>2DHA8GLT+|O;fb#cB*vM'
    'Qk3s!zgeMo>|%<%3-m@;l3OM$&OXMuOZsba3tDr-flv<N)NfGq$ttL1$7V(#{y7rj`;_X}-oy5$m+IK=N6kcM<6-?dDP(5x>%nbD'
    '@)KN0izm+GB~fkUKgVf->7^2&%I`n%gBhzdPN@2|DDcx{AC@D;rq{YuQz`S*pX5<v-iPqusSX?nbWM|QqnaufN05Gt7!zGKCguVV'
    'BAhn~p5jb*VsUz`#SXQX6i8sH&n-_ztrOBCjjGP5l7%;PGnF;jBepfqq|^Yx+^7%NYk{5YVQYZuR7_4BS#E>BCPWVGbfE!18i69Q'
    'G4-4AJ*y`1JA^W7Zg8fmqaxLZHFLHGH~5`2<c$3_II!3IXIjq(-mXg?x?r#ej~9T_^D6sI3^!()v|5YU7TV2dI_jE_A4_Wl9*wH?'
    '1`MO4JKku)N}$VvWToPB%ZzXbkjHkZAiLpU9c@DN+N7|f+|mRhbqgWRC26hg9{R~gzp;E@;#A{ePIJw#dZvFoQ>gvDGj0AVWyM*L'
    '=LQ90!&d1~XZ@9L-|5<iISQu5rYe4@-f33CK20U?FmAa3V=>7&QzW?`w#Nuf{rDQ~q#HVMyVeoLW14-j^(&Us?~NDu_8TZxpZf)J'
    '?_ZgrWN;Ws*MX>8WjRUAmQy;nr;ZTN<{2!%{`3TQJxG9XKUX7q>@WHw?3!LR)!(}Eksm{kocQ@M$CYmLe>}c`0kFXh-4eCr(6*Yh'
    'n9ss9_AF%!kHXl(knh&|9q13*lBdf5@7nS7#1H7$T-s+r{##<(<jI~~B561lFTEnSvtK}7JQ{^vcx$!#lSK~I`ysVLf6-1f2>|sH'
    'RPfZq$|y+M97RtvOIwYH0VpC;$Wy&}Lc+ih5Al|z?n?-13%C)HFt2QZ&S=#gDf;c4>h(H8!28*0@z1W;re?KlG6ISZAi1f1wN~-b'
    'lb1}4CH@D^xvoiuOSDyDh~U#`FUsL(;Dy1vep8l-`XtX<s|TU<7)P7P<MI>OrTKuHRmt(&HaLvXf>bLvif{iKnzB8CrEn~#9N0ti'
    ';ArBDC7AIibi%(`<JQ)>S>d|*?7R5P9AM|Jyu_C(4+X{2m1Hm&Eju;|u|^!uyMedBOARgzaLjOv{?LGg?gfD=X*EUVS+oNFGYQOI'
    'eiv~K4jpC@r|e%Gn#^d+?y4;$tsE8oa{VQAx1(!2l{V)`ITLZS5q!r^LN9nLZ@2v0Ui%G#Jm>&>`z?{Fv(-<PuXUYn3V;L0Dw^}='
    'G!ia1m)9a#ez(rS*iceKl8{P`-b|ObIb&DLq4}T7_Ja;5moru!;iSlKRn@N2cL;<p6pcj^*;ZWHP<rdHZps5H@GF;GdF;2x*l2JW'
    'QoI0{P3&ui105XfmR6QD`g1{CCxjS2+kgz6j=VvP<9A8)z8`Q~C_OM9^wju#EbqXn8N%FW4R`l=&-l9XD$DGOMgi%a0qcD7NYz0E'
    'h(B1wO078^9N=l0bk`s6DM)1CP-b{RK9;Ys)arN&2IRy8Z1UG89rw$P2uJSjmMRQzE!PyDd%L^yX~nravX4LGz)7%>^&2Hwvm;Bi'
    '2dGWg|1XKFfh7O_XCi1b#hl3HS3FUH>^E=z8&{8}mo54zhxDh{$l{+`CJcugp1uL;mom`0Yns>d)a=>cDX)R3sfMFW{&ISJ&^E>@'
    '@WZM~=4N$lEhMw)ce&(LC6j=bx(0eID^mP!(vO#)C#K9#B0f$FJF|dahPH9Ow~c;EHGH|ADkE=?YMDy0r**LqB-Ibvb0z6cf;}96'
    't-^^ytZA8@_LV=0CV3uK2est)8Qp-ReFV?FTWcHT!{pqb!#n$lcQW3RT@s_SXZXKmi($E-7X2&EmSH$D0Tp6gJ(akV685WeJBLZP'
    'Y{?0IEl}zIncO(2zu3SVapUh?X;Co1{o?f3U{d|iA=j4wm`Mc)7V|<@Z<>xX%yxHy0hmt*7$I{>PX+u0oNvi$f(lR)28g=5S^#4s'
    '8sO!q%7&?ueY2Ba;+Guzh0@8}98ZR=B;Fn+2|vsxt3b(XI}3ES%ZW9Nsu%ws5M0~olnNQeFUr_#Jr*`h0Pm75x+K|v#Re#X?Xk;p'
    '96*trE<!l1_BCh??~%tW|F$o*T{?|+zs&-+esaXY<nJO-(1ez?YHwP~AlOg}#sp9)=kUUbr${9v6LLyj>{(yA3`dlWiPEFIWlTL5'
    'KK6{BaLVm4u}=Oa1lUl!f*`_yy3)F<pQT{;a>bJ+&LZg@?Cx1?)@yqsqFOngnbBg@PQ!f7Gi)|#aQUmBflRY>Q?BmuV8nZQPEK5l'
    'HC2L2Ry|Xl^(3Qf2Xi=iPp!hlI4BVLU^J9{Q3~-Lturer&u&gh{|4d$MUhZ~5Xoi=Rg6*2D-IfU|2B@FCoy(+&iA<*-%BCIN0R9#'
    'X{jt>X(#W?#5&pFMG&|2{MJ`!G{oywxJ~;|wPMSK&*kwSh?P5&h_Vf`r<aP!yxdprd%ly+F;7dpl#ZBP@zjwTU<9^FC#Mdykln`X'
    'CitDWOa;S9hCu&Jx*$yQ$f{iaA%lDHCensJZZD3X5BtWPkry;_wN)ug`%DZIZ*OV(H}_1;ZJ+)o**Tql?0So;LzBPZQ%)7@an`n0'
    'iy*ld7$<5zvEHH+ISS3|H||Z1g^G+rPYeEwHQl+w&_+*w8ifHJe;>-u8F4PQM;-wuTRK5Ey3oKGzK0C(8X9vGRJuC0I-T{%-itQ~'
    'dxYrmZ^xV}pqO^!CHft(@8`f>FVSN^qh^ch!6~7Y{={X_q5NyXC`xki6X>I?cfSrR4B?T%xFFgBqB)R}6qJU1`mp@V&V?LExDO+S'
    '_B%jT{PYaKYuP#6hzAyf0z$@`=J>2_YrJ$b(7uXjvh@;>{mO71hROm-J`SyV)|s;qLgI>F8r~vB&d22s`EF7(K}jQ4VhZEiwf6Tf'
    'yWPCBI%QHT4C|;v<0(l2{wk;{S4UXJnUGX>QNQ|STXo2{lkGe!sQNpm&^<uVN*XqE9Yai=vuBEW)MlSS0u^A~zfC&GPzAA$2J;^Q'
    '+!wcBtzeT={a}#8q=~(V&T16(VEEDKD72v!#uWGeM;}OS*5Z+zYXn67T$UO~^(wY`ra|j8?CL3^?T<T->U?-lpt-G9WO)1QSP-zN'
    'lJWeYT6+jDDi+^cr$$&GT->Ej9d4Eomuu3pu`O|$9euvmEf2YnHnK04@&y7Ng=-6-OG?LNS8)c=3ee4vZ|e=B;K-zNyAe|D`rd`+'
    'j6X3)2LH_7hhl@-%+Lo`RYJmWH{aM>PVJOcrBj>gJPM}Pin+r&f0x(_F;M+?GnOWSd6<)qK8v3fqR~S46;0-cY~Nd$fTaXq$Cf<*'
    '!`r)Q=m3LRMf_gNL5qCnvBX42DK>MRz5GCt3l2eQ5M{#p5|rdcs;mlZkIq`hsecc!hW6p2rHFaIeE*bJ!~7<TUlKCx48ddg^d>&#'
    'Il?#3!xV1V%S9rHTM?HL?J9;}*D5R!@0e9*afaPq%3oNl<TZ(>{i*rx&@sBV8lS$qw^Y31PBo7DIBlUhT_<KDgBxZgVtp#rwyyq<'
    '_^UUzWxhfY0nJSlq1GPZNVLPk^1O#wF4%b=Mx!gKp0>-Y_?l|%z$2Fyn7lA??rn+4$=}@_P2nopTi~>ujdNRJ?~U9!=$a#FLOT6E'
    'fMXnw6F^z*Oy2y7s83A|)TpP47KZ%<psnsUTT!F+hJcbSHq-G#gR(pxTTrqgPn$^IC0W3Z$}K}}m9*-G@^NppTMC!x%FoCZ6Xj0!'
    '+3wo*HvwWhV?~K;%siO7x9mqJ`!+cwY%Jo%kZ2wu#jj&jgK;T;J!YJSrvSU^IAJCPSc~3tp_%_Nxpxpl7ks3h`1(K~CWgm#D1oVF'
    '`93d(iePq!2*sPSavK{d@9T<QH^~SdFzhKIs{IuXz_ggbPG$~|(92+u#iP=)nX-Y#_MN--00Cj@iW>j-k$XWcb}#m2PP#s7t$6xs'
    '2C1!m>>N6Bg_24z?8um7DujN1SdV>XyxqGtg?YFa%naF=m=aB``A$>(%Jk@YWfzB#v@i{w$9g=eiuT>ime=j|Y9;l6-jSo~&0-Kp'
    'SbWT`qqYmid{0KYCi9hU_)Hj)%33>V*c65zPupqs7eCn9xy>i69-*{_tlr}yUQh^KFfL><G!qX5nbuEg+zMzVChQfee^XE$tb&#&'
    'JEI%JZ>1E_NJw(ugif%0P9q;rVU62EWw=}8ZfR&3{rj&xR$uAhviak1MAuXOI{T$)c9h=djq*sS-PrB+N<2VU&?OZq`hMjFC$<o7'
    'h_-Dk|2rbKH5yO05N$BRc+f@3H05+{_}rUhZLP>O@{Cz5ZH_^u0|2n{)L#GEY4RfWm>dapgh=*syxkEd!vjtwfeGUxGfH0@u(Cgi'
    'W|j@!J$r|D&FMFDyZT=;9UMpGIsmd-vh}U(3iO^8un1nz0_h@FqQY%gM0%A9^j@L$hBQkoPS9(=Ia?vfiP#=1$J3Q4GQ+Zn2QL=V'
    'F`=c4K2B+WBHq%8f2%TaJri+Xvm=<Js}L{qY>gh*Dn}F5r*Ii2FbE5i19M+YXQ%xr$|nY{?H^bgd(4kJEf0rx{i@f|bupEQF!Nb~'
    '_f@<pcZ{5CZw)17VBWypPexRH8T!*X_(W;aSEo6Ib*7xEaUOEsMR4rQjX@(wvOdjkthlOv`I56dIa<$e6$MI+u`9_!=E0u<;VF)w'
    'W+veT{A2Rp?wysreXt+P>%JaLM<E_6F>-UC25*e~UA;LqzPwT!=6Uq}C+tW?3Un|?yIKG%cgehT*mo)nYU-`MFvC4puAETnbmN@@'
    'xip8K`<ZqC@Ok7bYHynj1-3Lai|bBh0>tY1`muhUnrN|g`(IRB#4Hy^r9XSV0ExR^^_qgCUS9w7i|5%RO&@0e_q+egf@p;gQ*iCA'
    'W{|p0!sEx7<cdO~tD}u_H>pBLU%*fdiV;w>d_3)_A)z)$dkUYCv~EGH4_w&Bm3x@c<nV>xxz;W)g=o|Of(a6mn0}2FAACRd$ah`D'
    'chhURcZ4_f0;BINQRbCQu7w;^ZkyT_(yl`vs0mN{x?0>FHIIFY+fxOI<KoZ>qK!y|xZpWXFG}*J%eOg5|0Q$<l}sPk6-z>hs#04x'
    'G-1Ysi<*d5c#Z<h7x3I?+=^32I^QVU(s5-TjFVtLmCdsrE<=<d&0CkU{Y<k^3s{reJd6NH%8bjYM)?1HpUxl-dMdwW>ehGyB($V{'
    'fX^zEr0UOMP`S5&f#Ze9Is&L5vc3dA)wDBDbv3+^HYuyxN7QpHY`PjqN_>tmVeT;z`BGL=)xm5hTRdb5!f9zroO4?GZ{UF4`K2_;'
    ')0=pgNiXuFgPDDo_G&Pzn=}q~5hFg}jmmc{NlP(dz!pV+Y{`coQ25x=p^inA>d%L(HO2k+w3>Gh+w9vz@&ODS)M)hAT?+%6xGm#1'
    'l#0tgBZz>)g|QRd8@DC_^LD3}ioK6(`_h;vvNApR?nAPpFq?AWN#s%12d-(}-3wcak(>j4sQ@ss=gYY}HXHC@?T9`B%aVIVSE<DE'
    'BRy?Kc_n=uO5m4InQ#h++yETwcCigSOg!T_d>SbhGbnoKXb7K*@TLFqeIW;T<T9R2o+!{*$z_D%`aPaV$9=zl*N&7VJ};=gdfNnp'
    'iBf9B)MV_Ln-Z&})kP*hbR%*gdKE&a`{J9fZ0=t0?_G=+A6!guqyqe+A8K!ATZSd)ra{0L@s#So9BY*EgP8~A38FD}cjxt5RKTsL'
    '8uD=##%R%KgWk2QwzMGl-4j(BS!YRIOD^)2Gxq%#*x=fHokcFB5PpSRtW1KRkduDY<+eGnE5~x%X2#^%@-e!7F*zg^{H&z~x3v|S'
    'AXB%zNmiAuz2hyc*vbU+;K&{s^p_NnhaSw4;|W!;6mY(vu!_er%8SRU8(Z=djK4%h{!|DbzF1zM82GAFvXrdJ#N8>>wbZxh5L#Kh'
    'uCzB_%x-2GiA>y|E>SKT8r|cEaO+43G~%<qsQIOQm@yCb%kCsj?Mhz`Tm!G;wPKmD+-v3h6D7ggh>d2Ie~hhwSCUG6Bv41OAzboI'
    'uYNXM*=spo>AJVZWJw3&>&ZU#ASSPpFJE8)AK~4D{3&b7ei^&k<+LB49}O5k^O3(HA@frJHJ<~YHgF8W0re^6HdJzJMQCd$?5hAk'
    'XnAsy3#FpM1<#by&XRIY@YtG`&7u@zC~1unXis_RRwi~hGa$f^sq*|>80G50-L{X)z<ortKaGl;1lui};pyk#R4yr4BpsP4W)Xr5'
    '<P#tekG8Le7?ps%zZxsq8`o9-o#FgzJ^*j~D>pd^v~A~f+86yzw+(U=;4jfoLRlBAL47;cMe42m2>08oiok7mtgnA<dv5zv{fv^l'
    '`Xb#e*!5RsT#|*&ef~8^_>+G}YA-t@iFJVViWawx*7(_nU*k>1%zm_NX}Y+5CBEd=Xv>G!Igirml^~KSQ{YzC=N8e)RUlQx5|CPp'
    'Okyk-+G=hYxkN}U<qTUYf(vfoDiXY_lUD3H3}Y12-ipt%2D5G5+O5HjacaN5z0{W_Tv1!dY~5C3ny)sjf(fjD<^<Eqi3aW_cFDg8'
    'qc5&XQyag+_zxwh^gy$1=+8~(LPu)9CV)<67G9M1uFWjPV5HUKJC^Iz8TYdp7FQj@AzSpskQmRCDq<f_`vgX50yoGvDft@*Eb003'
    's}-v<DEgWd7`gDe_}Fip3xkK5hIsw=_~b!Ow|>0Re{y(uM9xlg!hn!fxEUV%&gb+;gq);e4cbj<jps4i7$jkOWG&<kWP~jmmdxCe'
    'ixb1Kk;dI)5J^v|bvS;P?F*3SF)hA?3M3+>)t7n9zJ_3n<$7a!ir<`CV3m-h-7faX2@?3uTC#hlJ^1&%F|rc2^TB#V`tO|KKeQpv'
    'DY`!VtZ{OYk%F#j(ZB92v`(BGqfj4wws@V=Z@J65%H!K0ECOZD2GI{d;@W{vZwf+4eWcD(@}G^n=MI&WP?r(gMA!R$OV-54B4CTC'
    '$pjf4Mjp(uSx(Y<^`Bb2H}QsC(cj`ufHmb0d`HEtM!E$<-2)mEHjlI?_fXAhIEw+v>Q#<ZqEd`ANs;dYTZjnK3UbE8NkUR=FD!N<'
    'd}=jDF=N@0qF8kl0GloK)IbT<<J0;In{6ms)Fp&$Uh#5~FCAj109CzlhC=s<tM2+tp)N{IHxqFc1Dg+K)Vf_a^<>?pRiS#-UL0#A'
    'm#X~LWF8YNvBU*uaG`P==S@noj1s?qEnKegBKVKjtLcLLuDFiK3D)tcVwE>BAefNpKy|Dt7=hN#>Pl$5&?E;VGoO~JKKKL4_ri|i'
    ')r0iqd9MYK!16K+M9>q#btsX`=lCy4hc9Ycn(6+*^Mz5-UHM`*g2CBq2&BG+MeBxT=OOOtIPg_TjW)c-am<}*UHUN29kMt5F1iAO'
    'L7L%w!E>(}n?qAV{dhL0=&y{)9w2F)gIo&)TCb?w^~Oo(hjH!P9<Y71c%{&aRH|&lW_-(e^vd<-!eUYi(divyB{H24xnIdl%si{k'
    'i>4fsnmXPg2%}D&i_6Lu|Ctf)WnOTqZRI|f12g8;4`-i#Wp5D#uk(>?O<#$xgY35#t(Xo{qhvewJ2Sus(PagP>L=sf6Yq@5J#&i+'
    '3V<b6xO@EpJ@^vlDEEs3l;a72>V|kUz(XG7mDRd&haG3~+4}wmdtb$1;#{hp<*~%_M?Z8|@y@XG$zPe~B&i6R^XxtSE%#(N8{P|0'
    'uju!Gg9?dIi>k6SRaYnVGbs$X@T>64uXwpvo^6(FBlNw@>ZQMnxCIsXFS~hyeWlshx#`J4KIHOccpcik7Xs*>wi5ww6b>8=NTsST'
    '%uwdgiq@!mvhp<U6A*4*CEwx;WIicJvCCsG&^S*YhKXaNMB`&dq-&NAbIGba3BHm1NVMW>;v5{L&jqQNAo;9>{@&HZ$x5equI=iC'
    'o%`7A;72G9hq&```n=*4diyF%&f>0}=l#Ljr49J%Dky!#WIt<&eMjPS`KssI$hriraGHI2gCIE*D)lCt8}wRg*HHN0YB+#&nQp}|'
    't=VT}RE$X(_<J^@rO|W~R=`A2_4Ql@C;2%Pw;qB{m{ntO`F#d6mYyDKva03!mYun9c1yjjIl4)}Wc9^9DtTq?Vim%rBz`kLsfZ3$'
    'Ch^zoYEz_*&1Di7D)I>cE$-g{^+Qs0YG)`Vc&33S&Ld)$KpC(^dNXTH#fPftuC)k)Etx%wJhIQWblae6kQlEC@AseS<jn3JtIOF;'
    'TN>NKG;KlK(>wD_0c@rCfYo>g+=SWx-}4K`$IXFHw`c(;Cgl{k&quoX{SDpyrXYxAKNc!02Xu|Bu}iJU^O{^8)Ceh{xt`Y$Lqc&{'
    '>`VD~&M_Nyx<8MjTV_9dNKI#_?jsF}uz_XPE)|TnriVr->>1~8%i=S%7v4Bj$x;k<W?+IO=i4NeLX}5~-|h0|f^Xrr|42fGj)#_v'
    'S3W1WDlTWs%Zq`WuXU+wk1<=@Xxz7k!tO8DxC=qXI|HE81%8bbV<tkc;t4EfTt(>AsoOx#@E)%+t3`#5-rVNnb?dx+K7<bjH<1{k'
    'bk3rENf0_X(o}^>3*#u{I(4C_i5y%IpDV$b1fQNWEDdism(pQ&s-pniZpz$UtRZjHqw^<2H(8t#FD`q>W2uTOi-1Gwax2`6HVUS^'
    'Ck6A;n&3ert(w$6Ejl&$-7nt5<E;q%TvvF`g848YjyUb)?;sukf;dFgLf1ysDVr@CC(&k4wQ-j9p)wXpnrH@1kg_v4$%HoAnIHI?'
    '8eo9rb2~r|fVUschZUloKihpsfNae^%p)7X$A4<J>>t($;<q=zHBaR!e{5+5ai;~D$-3*cT@q&(7WV5^Z7K=3Ty>7PC<(<o0Fp$K'
    'qB&baT4v`4_9bnfcf2|6!gcHW6>T(g=sehr^^g3Iv4JI=cABrbiAns!*=H#EI1D<U`p_4a|Jd~^OIHt?3)jxC%70Wn-2RZqVQ(ZV'
    'FzE6FE<6h4G(N4o;QP)`53#?X*A|vaTHyFd#ckbUC;(!=Q-!bCgt^&k=9f}2sQ!P#;aoAe9SqHCE~zly=>+9KnmPqoS)I&z4QF(S'
    'I+@0UFDCIkJojTk24JK}bX@e;m*0{X>C+{%!17q!Guq8ZTRPMK2he0}M_9pgN_D@_g7P`si>1fF5<({rGS6GwSA`?UQsXe(@9FUg'
    ';l`djv+Iiy<R}*jSX1<mvkF|+{nG6K5Hh7Lv|_B=v1@RiAM%P9zq+0qHH@PQuEK|`NG(u^MfXWlIT}|cbiJ)I_1EJ75@nA-;VaDK'
    'YH0mLLAQ4kGvd^Jd+b&LYk_^_H+=FHm%PGlhyr(0NroKbz)+KsU<y!=0ZnU-?K;D6S$K18y!gtonm4JPBcyY^*16aryP!2#jOJiN'
    'O<Wh#&g&NrEOSQ2wew|G{b}#cEGNbzcTQHSTBjx!Dlgsic4Id73W&wxqyLJ;E!8cJCT8B^q%n*V_ag&b?byPb<eioTl7e=I!rr1Q'
    'm?gy#*vIO5#7GDj7rP3!nqy&eAs2fKfi3ND7d_j(jXB#!doXw>$m-;F7qGqs<M!OX0QXY{)sy=dd%ePVDo9yTs6a`vC0$MT%OLQt'
    '3Wl{N$50=&OMOOtI=N!p#fZ*0#0WPBo2kpfxk%ULMfy|dpA<iMZMz=P<prejItpo;6xmu53_mbL%c&#|`L*Z3uGm_ddZk|FZ2u|l'
    'P>l!)Be1W{IV3^V`HQ*c%gOFvP}{+uN#bP9i8A-=aM38Ug%$0V;fwB2(Za;4y2?id9t74l{lw7CGPH*)Qs6@eoUXPT4Lg_Q8$z3B'
    'N0q=L(Ieh=is1{rD%$*Cw6_;f+fKgKxWkD5LtcM#9W6QPX?wjC8YI7YG>`BhhRq)4ssHQRAvhV^qSEs-hhv}WnIeWAtnnzn@;?M<'
    '$|C8ky<MM3sUtx4Q21E0XfpbSQ$Bv`nS{$DMoBa@9ifUI%D}AZX{XdLMR#%*a+&DZ(raR_$}dBm9;UNG0+XK%D2ySujn40vy|BIH'
    '8kK~ZqMV?jP8g))ru%M_`92lXR8+&irg6l2$EmeqPlFyCDmg%AFQR<9U<u3Z8p7CZKqHa_0#3=@I_kc0SC3?T5m!bFUEJR6XA`o}'
    '*Z;X9*FJW)Css-`Qa=5o;J-L*T*t|{N9fDSrOq(MrNeajFg;9*vKW3Zi+b~~1KgNY)FvtQwJ%TfPzvG_va&O50`Da%A#qBk{_}+>'
    'H*EjlcV8zA0?gQ0!D!2sY;f55L8eQ#Ry2I>%M}uZiAV~_K%S7fM~A7D)Q1CGeiV8tG@lnvt+NxUx;)~)Beyv24r;yOn>8juOG5`-'
    'Bpf9&J%wE!Wc5l_^ktgJkPgmIO-M>>G7ZL1>BP6pJ`#Z3Z+hLF(?*Dol!hGq5$iuTGM5&2qr|)1*u$}rLsAV=+)K-e2Vn9eC6N_4'
    'PF`e@uuHwrM4ad9@vW@aUpZ5ex>Zpo2H@x`<V%zo5t#)S%q-0S090(T7s3Y{cZKGla_=tp6~En(Dypbu2BFdPZJ{AeEXesm(In)|'
    'Q_0MF<K+umKry<<-V#HjBnq~1XhJNNO(`RW#nfjfbs#6~&meWFkU?s8w!wF%#zWtf*H=_UdWqa`zLzZJ{;Lt`>wU%TbcngC#4qEh'
    'DJTyK9<apz*sn~o`o`F150i&rtm-Y;!v^!8Y(>ioy#U)wN=*rpCE;rFVhA*CTVfu<?#TmbZ~Yi7&<GhoRju}|&seswV)IP}wlPgL'
    'bRJ>ZjZR9?MouC#WWlJT50z?+-upFS6XWw}1`PFuD`}dD1K)rpl55@97HZQ7vBH)2qO2~besTH|?3v~jSdr)^^-c#vM8-?35e(mC'
    'X2Z@WD(=%4)~i%-uk&lgVy+;73kb7`iJ)xGj1NJHZE@zK&yRfo>Jf4ANpMp+p20?s@rCvEjokBQ!L3>8Ol&5l2lhcD@a&k?w}5J`'
    '0*hHVSvd5rJ*GD9pu6>R^~W>ZFY+^LxwK0MQxb(@pfv)F-{+hwNsNxJM9QQps?H(cNr8)?-5Q?H(Pzq}*o!=GR&frgzrWv6wlSwa'
    's)RgCBoHpZB}}R?MG?tWhskpinZaU?<d6KBx^@8#6~vN@8(@Z%<01Uj&VH8V6beT%^n`L7;AT{f$4XGj_S7agMxXN41?3#ns5+5t'
    'WIK{E86jB+^9TcD&GNeN)U{cuc!kKSmLeVU6(Ah1I<d$dMNC=30;0xs_glTrlELjUTrb$d>Vvu_Cx0u?kQOBg1PW3s<D;~$KLdDD'
    'T^&o8a(pssA*a_3tB%=bm5cEv&q;dEu1gq+eF}GU3mh(Nkj%ujVZ(+Y@a4jP>a#rU36o48efr|dWt420_GI2OS2>wXxkHXW(r~8I'
    'Lyv+^gZXN-x5y7qA-}XPO>)bn@5p4=152hFLL89GC%?wqtw99w&c7e)-N?`F!h*!O(Xi8MQI^mTaF(2xY<QpH4Z_AV{K&a{lJx#R'
    '^MW+t@C*uN0>ob^QnfVbo1@@VNaRi@Ng7`OtIABfvNQk`+$Tx3r3voO%5T}VnO<QV8VSp>F6$;9e$5zfPvJ6?rwG0=XdUg`&cX7N'
    '*=jWQl~<g<OpKA87<Rrc4rU+hBj}^`!pRPy&m9(S;VlYrcdCHs;_>7<6Ol9>7Wj=sk;-JymEcvbGWJ*gYZCT8e7Zy`0Id9gpN4g~'
    'aLC|E@&01)l=m=DBpjk+@akY{J4ZnyBMJc!VI$My^|O?WoiPS0BOq%*tSQE)rPoVNsI)F`nb!w~%5Wli1Xqxv>p{bsNBF5#9MlV='
    'ud+%!$$+|}-58YMcRc8y=g*39Bq@gpVesMd_(%_pPZ*>aG6<1tyaxDSN7!&~y+J@YC7PW#T*4Hv-=;2r>CgW|ukAr)@v@{9&)4tc'
    'j^kzpgq&%gH1mL)gW#^9XdJRt@2m(dIE1{+SHD<FDHP1$FW~YvnKC3n1rl>$WPM{m=n-8cBsHxYspGFqh@Rhg69u1o{&hG^p3PO9'
    '@2-#9ap*t{z+<HQIlzuHfB=gD5$iDc@yELBBEU=V!#U49vFa?;ooWCBF~z~C<K;<eAxX9u5LTqQ95HZHo8^rrCtG{yT+kZbUBl1o'
    'bkZTJ5cK8F@rk3?K4w9GNbJsjHCG`rMSJ;72b>2E%^rF`?xT~lP7{F2_5b^8I((*{C*(W066ZxUCsYHATx-x-g-nfU`#THg#-I&^'
    '6Ih+^kN(}GD$)T>G>JV?fEq#wX$&N01W;y3I%<Ya%4pzCiib%ijJ{)@a|xPKSkKTlnJRY;44UiHkKJ*hUyq9!<f(}<dbNWCzsnh?'
    ')O-=1Dx)nCEhn9mhAk{W-L~xDIC{QU`BP&I1un7$w)y4)Q3a7Ok#~ZC`mkO$?aWMwG*;F+;vk+bYs{pYx<Ir^0PDg~DjWOufsFRB'
    '>ds{%r+L;snpd}tgMaGZIi~+iAw9@O-=Df+AHCw4Q2A*KVru=`ctsZ<bDmhrK)uo#-9o$$jkpM$wPW=VqsQoe@wpe<t>5vVxvBZH'
    'KSRTe_pxscyD8}&YA8r3?0b)57iSgMhhIUdvuo6~Yh9rvR$|%;`XC}@&8V;TX&naxMGW;obPSC=bZ}GfOO<aT$z41V|6h;L??Hah'
    'In^Plqrczf=B*;jO|WF#6B!O`p;k83q&3}inkMV#c@CZCHs%bcm%)mJleF&B@I%7#xE9;oRdgnbZitl4ucJhpt3)(ac^0Kl=1P|o'
    'q4`>7ex9VXhjfa-<_aOtENY)tqL;s4sg`&(1oCxc>SC_RBejEd00xT+rl8}Vo16YWFe1P(`mm^M@gYEgJbA9H*}A9jFj4Dz*Q|I{'
    'iYI%Io2qdzCTM&<3WJr`hp~O+c+tqVUh^l+q=^I=XkwF{7XCXC&I{3U2~VCqA^f<xf!T{bZ#LT8t@P|cvg)gdR|OgQBrxDd4eGEO'
    'T=yo)u2Uk)J~GbknE8CvOjG|6yiFNWBtIi_4|Df2AQ%TXMc}}Tp5+pN7B)ba@$w(Yjkv#o;)X5&r`vC2x}z540s+?+0yIMXiHp}p'
    '@kbSDxg_M6Xa>%&iBwVGt!~R=&eujDxv&WJ5?s5^dsDHwrya~Ih5elGTwxgx1YuN4I69mXC{kSI7%2dmuB=0O5s)}}V5e4^SnPfL'
    'Q6)E>;UO1dzNyc$e$iv%bfm+gSyc@S6(RzEdMX4QQ4bYWcZ>UGd77OeeR+95DYH<*&g5%P6#3;5zLM`YPbx@UX?&C>J|19%MP@DJ'
    'djRvRe7u{E7-w=9+47BN3dI)^jdXE7JI&)(rOK?5nX<BYUDDed4#tFCihN~oOs)~m^QN1cW#*7~$pd6YbH{k+=P6}86%;!S@wU=F'
    'XFrTMJtPju1)*P38(BcfScvg8F7a|haXu?9obmN)`pw6j2FYkIR!+kFLz5Wx#KKxKlz9%B-SM&zRUcb6)r2tZyhj6SBzr39LV@HJ'
    '$M#7#KEvBOZg`;txy4#iMDbuFaZ<+oLH{lMK@o{yq1F5yhmDCvQ<4Pw0$J^?BYV|^$NeZ|%!vI~6jh|{BBCK18!+u)Z{v4zm=94R'
    'rUiZVbFDeNUzW6$2NygOHmrQ0Ol<9hur-k3bVG5FIUaEsUr^X4qGOuEs1UI3jFzJ0g@~;-?9LH-$ZK`&kI8{_+wRW}IRhwvO*$8X'
    'VmYqms|hAAApE#dALchx{;b`_Q?=_n8Ss|^O*K~1a{-&$J=<OWg|-H4ki6~h-SR?M?<bs|Zj?S8SG$-Pi#k{HQ;6{EET4UW;`xgh'
    'cF+log^1jvNK`VfGcbW2ugmWx&m)IhoEhd<gD>Z^i%iGY%`+!p`t!#Ls%LRLXGF$s$Gr(C9A<{JworYX8#Q*Cby1lF9x_XHJlfdE'
    '&xy75mkf{T!}K$#eSsiOn1PCv)Su=^zoTNYs?Tr96Si>)s3lI8Z64QO^J(8f@^EQ0tbDqq8#=XHCkYGVRWtnbaBBz&Jx)|sM|6kn'
    '#w3{@2CqQyH9VtXQ4ixeo)@l(-b5Hq!CScxl|x|BAQB}ICVgM=Pkx(&@h0>8ZS>qi#oplN&;5_6d%o%x?Pt}y5P>rH{L9$SFPb;*'
    'F4-R~<<Q+*!jsV5US@Uar=w$i7%m`6H8Q0HFq)o&DIm8UCAC~;YMoM9E{1E1Ppw5EQ-deQzOqH#!?wWxe5QIZO?Wd(@hs$7gXRfF'
    '6l&>TFmm<*CRu-#f1EKvr0Tnq{v{VSQ$gKIQ<{K2Iu;5nGrUpkK*_Y{$Q?xU>lzaIwVgUyj9I*?Z-~mdZ66^-prJqsO3{#bs${Nz'
    '#V|We1|lA=<GSbgH(JTVzj!0>-QRQ~)5#*gik(Upoc^VsF^s&j)N9&t_Cd{NV{l#lKM;IpO4F>P5YE_Tmdi~5^wm|&hrU^)FjuFa'
    '*$~)BoQ@#<s3wIhC~C+z7CF@2Eq1^c6G80Ie`BX^Y9OwCs+amjK`e;vo6%V0+TZQ{;tb7J12dek13TZcv07X%vUHx+kLIqMJF@oM'
    'iHfI3CB)zwO6N)uY&Z;EYFgteUuVQ1V4AH}pw!lWTdG9wbsPA>r!W4@X&K8@9jKEtv6y5aU@PpOXRkS!sh>_<%V;chI{z$|QD98V'
    'vTlg%>lF)C$GlQ8Cf3Ug2jS*@HDt~OsEZ(gAcE+r^vDOG8(?tpFcWBiOjIug@F`-v^tb(;Q{I%egf>C%tKYkYMndYk*lbJ6FdHOm'
    'Zvb0^>jMHDN)8b-%-=cd5=X<WKBxN6ct=$^?yw*1LXed_Vr>_^Aa{=o%j?;EF8mruQNq?jiSh^X$-D0Z2l3ly{}u<WD(rwZtG1zb'
    '5Dy~<0^P2Oao1Z~h-c=IK@S2v4G`o80wYnu>YamqfgC-gYBF$q%Ir^U5;ClPm?16!>|L2zMtx4oRR>otLCLE33_Mu{hg$?NOu_-~'
    'GtZfkOth~F+F*el{>Y2vKuRNe5jbp`((fS3T;zy8!SK(mI3{40hZntA0d1{~i|<Y0QEOlOSgh8!)}YW&_KQ-c{!S!3xzoUKY*nq*'
    '&ag+@jd6!nkV|Xu*?#SsfKmw`!COe6PkIvR@~yo6b7nCt9r(L?bAtq1O5Do01#CznTb@4sfI6gCa`x)Ka<s4faY`bT^gqB72&U5e'
    'c=EDr5{c*qHB4_7+mD>@wT&yYU*&_>6&)e)T&*a{PsggxkJEB!)<q%J$n5-g9^0ys$bMTQyt{nUwcp==V5!cDm!wTEJ1k^FsRG^@'
    '0?HtD=dAB7ROGW@ja69eUIcEhs;;md6Zrp2=F98-#ep`2`1?ecC>!nZg?{{8NnxDeuNr@+ZyU<#WvR2c|52YMqcMD$O?ydyDJv``'
    'nII2;<Bs8mvc?!UJ@aBA#vXdxq@_d_WrY|Y(>MiNN2W<Y+FO}C(0qTgJIO{Lg&WRu3hj}OQ3kbXMPjGi7)10Uo4C%d<M{6(XbmYe'
    'CdhM24VMbN>Ks9X)3)aD5Qz+FrW6`9ui)pDU>S=8f=-F@2gK}O>F|U!$`QiIrkb$eTQkz}hI2Sc!3+*6^>`i{Lz8qxo<_F0e^-OY'
    'fAxCqK1r@PD>VMDm3&+4d!we*T%cmk-unNH8ey0_Qb-&CgPaPC`tDg-E(_JL`ki5ZX{r&5&I5>P_8#oj!=lZo&gLwSWDFFKZWoTA'
    'H{;JvJg}11Yks53F-};}ZMquZV(S2pL^v`=ffkvd{RcD>SvQNEA!ptprnqdXhb!fn#TvS%d*=vzNn-y>7sk2KZablC$~W!vNnMHR'
    't#(iI>5WH`54r$%AkEAFxL=CL-ndw@&5x{N5J|he@$JbJ2U0m=pC4~}!#~xydSXl%l=%3605QlTN>XAikEq-JIa`ig3mIGKdRQYh'
    'CJjoGXy5!>SAs_ok{Vssg-JuoLFi5!ex&OALpZg4pA9(R;K+27p-SNk`?gD%9!hkF5XSRx5}95eR=4uhf4ZA;Qy>0gjgDlxr_CT_'
    '(2!Ha6O?iJc6NAwBwk4zz*;IRK;Xf~jo-sTC&l%JnJ$w8IQP&WA}|)#gn=eir6x9=n}n3E#AG4jJ7_5-JdWgNV|t5|7h4IDxF1&#'
    'yJVL{!p?~DR{>hyEe!gp*e+{P2mg1}#aE9KVJg66IM|9Xtk}NzjSDjarR}gagpG-odx_9S_XvMZsU1yegupaI{ES@Khoy#n`IbH;'
    'R-6hi!Lc=EGCa+^oQt}WB;ZLa6ps?AZ34^rAwOh>^!D$bl>~_|E{9cVYhBj@IjT!LBbXy6z5Wv@h8E#>`Ojucl8#6qg26U9L$GXK'
    '{1SlHT^yKSttGo8b+{T&w}s0tYx->_)jV?=p4{pGYu%Zo9!c2#uyEI2^r*0AN_m34%d@)4m?Q5X2p!-d<E&`_D@4evpS1{?mfe*_'
    '1$<kqp>1K297T(vYrv#^Fj6br^1__~EtF3^HUs_A*=+!WgDsOvO|6|dS{>(c{Q6389QPET{IfjjRjzSw66kGafzQI{vdfiO#aYtM'
    'Y6*_$Ih`oTDgo2wUqt48lezMNwBb1LK@bQQXRzoV2uw6!v5{(Pq&oNbXzz@&-2rj4eBsP<@0Z7+Rf3aGd?Es<@RE_@c5!1(@>Y@`'
    'Jsj@+F}G~)B@DsTb8g5zZ46C0@K=HIBe300qEfxy%hn<)QW3FNj?*Qv(Gk8)SEf;1cd;CB4a{%mSV{*yhd>>&<Ztg`DU6P-P=A$U'
    'PlGWxba9|F9x(^TVFz&bQa^bjs8z3UL_mUYt$EIjgV|FWZQ&-{l1{p-w-(lZDuJE;jldooVJrbv?W&T8Q;yB@@>H34Ta}seqXBOo'
    '|JAPfWABxO7@eqNgSv{~$NsK}LgL)BkMxmU+y!mSMV{fLyvhEkvLywf_tK%KQnA9MI8UY3imhaS>=uUSX?uf@!S5A-r}86U{UdYu'
    'tf0!vvHO^<HCj~I|9JdU1;*5VQkOG&cB>_RpWQ#L0QSQdHeM-071T9_YX_}Q5t&|J8QWjHM)stq_f<1Y3)~K8aq56m>47RGD)ogp'
    '+1@+@py}_PaC*R9Sb1MNM8cL6TV=r{3o7?1<|f#^sA44&|KSE5W`9N(lP0oM((jU%kLSQVqgfb_ZA_01W5}h8POWc&b?A%I^i8ei'
    'rFCDlU&bEal<g|j(oyESiNaF1oGX`CYO=APJT;XyG$x|s1a;LncA)<mC725H@p)!PlGW;!2on`z*<1aA?{f2WTgIvG-BLJaekP45'
    'shg|UZ=<mUD0Dm3i6%{Y=>b3RIKIjZA;%eFVmQFl5W@UK$~v_%Ngn{nM8furw;$AASgrw2&>LU!Whwy)(t*v<z15&SZm~-%G$56A'
    'Sd>KTB1@5F9eA^3Am<rD40}Y)SW(T~qTwIcQ!W8|MGV(cp=E^yJ)sXRbCylha6CNO#N~Kck{8ZGObW7o03A{ql2dX%aS6>zlc3y2'
    'qiQ*A3lmqnT_^r+e?FO?)5j%Fg?AAsn<$$VdK0uD*1+h2Rs}!)#o0{3|LBbo@Tk%2nS|E<smegg;TtmJ!e#EEQl$si5KxIA?TXTJ'
    '`$z#-svxa`8*vm*BI?hS+j%H?BGWo@$&E2viQO8&Mvg9RO84|mS`{v#&K@O9N{u+9Qs)PaCT7|}nmW7Hq?<x9^;g$WV+0-9&$tQ8'
    'HcEZUa*QZwX0N(dP3o@sCE>tH8_cA#ig~XD0{XZG$R5I%?f7S%vF7*QI)q{RfX7@t&(9SmQ12eqP=cV0X^~Iq@Y^!Cu=wx=TWeMy'
    '*R@{tp?JG24GH=?W~BmlOLiWDSd*kNl!cO0ayN4L{&l33SmHpiSnzD*@QQ()GP2wg?_A+*NPAtj%6fH-4+9H7KRx;++?z~ns=<(3'
    'qvs}@`a>7N>q^j3I5tvb$r(0~hM~_~tPh4#2FedHJ~5d-Do14!4yQ(p$FK11ewmcw(+8iFrel>(siRMwKV#}7w?1w>S@)R-L`uaq'
    'yuC4>vnT7uOyZ0|R%M#(#`}H3QJ_z!7}Y~Y7SlrgaX{3uxi&eb<e@E0@Ml_b5Xnqio#?%L>=17>#ozz^`WY#C=7*Nv>+TYl*XnDc'
    '#61NdT$xvF0DReb@qZ+ch2RFIQmtx+@mV1d*(J4I)xhY$<?GGGLK#|C#bT7^Mq!4S{#|-C(1POd6qtF=t2s&Nd1zEGqt0|ynGZv<'
    'J8Y*dopm0S3OZ)3_s1&~!gzed#$3kAeTld#j$k**VKn$gQFM`*)D*@RGz!H{o67mlmqEX1u><@j6KD2u>!I?W<6EW9fG8)v{8thP'
    'I5IEvz7KKCYb+wY7{ZZ;yQ~ZdrE<rv^wtywh!|YG+Qf6pZ@Z7jcVhE1&A=&S_pFjcP*$P^NskcMsKZ7lGSw)+!O~KT4o3^`URXby'
    ')tTHd^<1@<Xp!p8x)%&Q`{RXU%NRO{PCn-3qSc+^_^`{__}r-fAdZ)|(v{NQ{pXG{O+5+u-5NZj-Y|HBOMT~^(Fr|E8i8=l;vDIw'
    'L~NOfv<wzwzyZvJz_`Fs(v<$BlM$NO4%!mSpt`i_Yk+{eLj}+MzRJ$oR^#w#DT8}$+J}-LQb+QsTY>Q!{-XmTz|gq0e_t*y6x;WD'
    'H-X<uoY+Eu^L71+nEmdK>dGLjyiaZwco&?X6fRiFQ^9k4rzd_sv$tJ_4kn!MOm<*~lqwlX=`j{_tTyE$;Hl8Mh~^AJ18|dI0f}M?'
    'OCm2x>;a?Bk(wMc9f3&E0qI@0)W_ybhf$@z;=#Uh$YJaS$vOh0xQR$Z4RRj8)7&oWIESfed8_k5e9k<N4eF%}2!F>)Q$=<d?6vH^'
    'JL=N_ekIxzMgV7N9JL0lL*2*5gh080Heht@ve~i%fIicteH#&rhJ%h!+$XVS*6Xu%T|OG-^^9wR@2~ry+vIg<&;Ja1C@*LmP+Buz'
    'LyNCj-Vp9CjIv^9)qcdB2E5j7n}usbSITEEI%2ag0huBctlFrUuKJ|Bu=2T;ok}PGg`f~~uDwI8C#Apvvb7%#tud=T|Ao}%Oo5Xf'
    ')a8{B!^PJT3lVzGC%k`qaV9qWdTl2-mOEw=c#3Sm^e-H|i*xLq=I|Jl0#Hv@#MM!c-gJyge(hyfFel?6yntHBdDWu2WR9neN*u>}'
    'w{2bO9Mqt2ZXHH)=feOuXo9D|kp)H(=>1>`JKX-uA21C7i@o7|a)UEo@E$OhvqG(V)U9{8fEA*V6T#Z*POcTi#}H#~dtPIU(CpQ7'
    '+{xRVMuU3ob3ly--}dACZDs&0H^kH4b(xkNFI5bH$Uq7R(SnEs2)!c*K1FKLIp!AtF=E;s{rIya+!QyCR3cj)nil7-(Az(LWq0_D'
    '{IKY7@s-2$_`rl77AF4jpZbN`yfV(6b%ks~>e*nT{p#qESumxqeql_F%}5DWf67M7MF9Q!qHV3b_!X2-R&FL%@>z`+L3c+%!GnP!'
    'X{o0g?(9~CtwfuOyzUYm3$>6(jU}U^h?ApQsVnP>BMQsmP|=QKf~B>vcEOA-TXIEl#CDNN|A3xFd_87_n{Qe&yj%rFkd~`7=lcM|'
    'S28Q^s0{9&cciuhecu`lT`sV0-F<r&)r3vs?3zHz>+V~bMdnj?CsC@i9^#J<l|`e>R!tq7*T6oS)O}gmF5dAX|5V~oSkU}`TBcx&'
    'qk%&_KA+e`dM&)|W;(@WGDC{8w!g#bCKYeEU7+p6Z2eal!Bgl=3@VWR=e1KA>UG0R?qS~|k_S+uwuN4Yt)<&8t&<Xk)hEv>ii}+|'
    'b;_J>fu|6(Q5W)Vw7NT!D=Ka_J-~;hdtMM|v+Z4c_+Y)MnU|=-4lrPtmqIdIuVZeav{k2mk*O(kpYeBSvd&eD@z;8Z%`5F89dC?}'
    'Z1x&bM-U|9Btxz-9)iBzvj#4@_3Jv}_aYK>G!m8_j*l$MQDc=upjygBkMC`D5f}860n540TO=h2_Q|Dt$<Ic>Vo~6X`x(S5`M22M'
    'K^-yl3DIIMB$=rOxZdrnIA|$7?9&Iiu@*~&?VWt(G}=|PQm{9Bj{7R$!R+FlXfOt4%VO|ENLWouAof+vQLgx_IM#y9cai0X*lB(D'
    'l;IOFi2D?ZUIYf9;LXxO>X7A71MhS8>WEUHoB+JLSl8L)6&O9p|AU|1rQp0I-qC9bRBOce%D=;Pxv>fAW^4jk86m0dh3-FjzU<mg'
    'fZ6tIGF!KxP5!$9j}!Y`ogTj9+#0PdD&@L!Mm%;oc5*CylByE0JSEVN%%#>qa}X2O`)HS^%)3IE{Qz>KYc>W$`ZKa6P+;DC0Cd`2'
    '1SDeuDBuinW1#uIAy?7m@}ZA9%#ubv^*Mzv#2oc4Q=DO(D88rF&`)K9H<n}wYgM&><Qc$c#n!#p4bB%Yweq;tbZRg$u@}khB{tbl'
    'wvLiQiG)CmtDggL#^1lQ-IL(Z6`#^#Y71p2Hu5(5r3=@si6V)3C(eK`evI4aZc*>Qlb5KBl~~}homNupl$JZz<b#-?$sdhe%-EhU'
    '(9_)!{J}gL$+L|X%aoXy#h+3l7b0{!z>s9d4$qqZ*8t?r@aMj8kQglMzu_GXwD8SRw@a^zl>i)Hgq3oKko{T7xdPP#h;|yU#(w<B'
    'V{yDGR(gCxer0^ndUOL>!mumOfL#{xfzV}g+vkBz$OW>Csq%#%uAxd?XtyxYwELyPaB#_5;5Jkv!0uZb#Ouj0_nT7W+khUFdOsDi'
    'PS16U!wjOZD|8FouqA8e(}Eap7A<K@wLhzWh&^8;5(Na7#e}y+LsN|bOH>pV7M3*O!(bMHx?p!U9lVP4PHLLO5E()CJrPd~<sxKx'
    'Ytd~NNF+qQ2Zd@9in3&4-YIkM)#%EAkc*nzlacB}I_J9Y1P5NBf$~a(i}~-}PxmX=X=g?yQxQwYEyyn`o*9jeivQ~uzX@(Woj`oI'
    'VBLrRjX%nNRIsUINVDtXcP8O1tXE$e?8UmD=JLR|*Fk&@0+;9*N%|;C^4a|m0PNHR9~iS$nG_D)%JqG}G&U15kgJITr*v1{g>Pp3'
    'G8YF9V-1dNX+q#6P-Ub@9}G~AAh*lA-KNxVtoZC-84tFK35XzvcFiD^AOPQIPfBk}l;W20a`OX`MBmEgq%<z4r#EU3lU^cjz`8Cc'
    'X?gTfEW>&n**euH$O&?<`i>Jh-kuUdzvJ5k8tLE#?z=p{MH|Yln2p{J0RM*%iybNUJmtWDhCU)u*rcJcR5bIN-OVChQ2|ds2TsDf'
    '6*B=eE}8e%-w;G%Fy@YmkD<$LbZD<=0d;(iGi<hgYk-}r1WCH2-7CE2cc4K?a^S^G8g*x|$)A-zUld8)ZkqYL6~`{;`5s=D6kBm%'
    'XnwzJs}W6H3-BH6t6h*$XBCwZxqG|jn#cj*?B|TxEu1fi7b*XYR~xt_2HdUrg;BZ@h`85ssTa@A1Lcnuqt;RaKxXYU-T1p06;D^-'
    'E~=ufsxLcv@npMkHZuG<7)rkr7aqf0hiwWNp1007v*nHx?fD8XPWr-Jy>PoXhNaFCH19=(BE!^v(kUa7g4&F#r<IQWlJ_qzSTFY)'
    'R1sDw)=FGa;X`akHJ`}Jq=rnY)?K_k@8Rfg$z`FVAbp+`LXtI*gZo15d1LgP{wQ>rhM-mk=!9Yvj@8-_c+~IFv^D1}6NH>qBp&jh'
    '<*rU6Y6k7*g5W&wkjXvPoOL-XYgE*o3;qe_>7g`WzM=LcH~SEFNKkJrECev*a+LNgImFcAUrOltG>R0PxFG8s{tqSnR7;{;BWaRY'
    '%6%amRnlT$dN5d={};ndl}kUkL)^o`1IPYfE#`AV>mdsYDVh0RUg+-LxaE6dfA$38v1Fc#^wS1{m4b<F10U~hnEhiRF^n0#cHZ&$'
    'j$0wm>3h_lD-`xolW&W5Fo_B|Y1^&BcKA>keIvZ%gQyy+&rVCevR`k&B~`ArQt$utxSUFL=?cV*3I`-bxZu5m%&^Uf2n8gv@lVQH'
    'S)nXw(d7xbY5W*sl;GfA*WaXWyF9BLHI3h38)=C6!xJE{`V*e_znv7#-`5_UptH!>EW~Ea1SNUARIORGM%~{^bZ6Si^LZA{3kCfF'
    'EL5^#I>yg>Ktm6HM-SzIkl;xR6=I;75adPS?73$QL4^MNVg|-mAf3)Ho((1VUul+Xh#H>+(=$=V|EoraRjfm=Jw9S7b85Z^TPUa}'
    'BVKqVHCA@@WmQgN{S<1p{v>%u__W&U3ghl74LtxJ`X&j*v4koHK1$oCS&n!e;;3M8Xz|=2NDqu7Of$At#KXNXuis$t{t(P#ZOngY'
    '&XK&h|3l@R%`uMAK1}SJk6JNJpR+8;uEiCO*s=;GQ#Pg5pYb|b5X^b><ln{bCw_FjR_X<XAQV-n6SbfbD46D7d*j=q`7tgR9rd9j'
    'vWq2omi5{_0n#0W#WA#qi1pD*q2ypI_2Kbep_mv5XP1YCc)po(cwSJS_*Bs}^^I46C-u*HgadVvqGuYwiY;`rz6zZa=G8~u*(05!'
    '2<V6DNjvFUdajyHx=r&bG!r&txd1ZHHo0bG?-28O9l><UDyfU$)J5Iy!hwP0Azc%sr2&zfw!7sZg`I31s?^ZtSZ2IWAG`-R%kf7B'
    'rrR`WJBooa>eZg*Eg|@!;DyHc@xHk8nk|fQ9QWpfRc(INK#2T>ZPbq<kd%rBqyUNrEuziBCE(4{Dl9uRV?=VQvE*@Eu{fsxd5WL1'
    '9Km4fbZNE+C{6^vR2%QBF8d8<n$yefEOjKBdS2@2@<Iol>+PG%D71!t={g@|y#HRt)C71*HY~MI4qL4f$jWu2N_S|3I`$9tk9^rg'
    'FE3fM_BlJK2>2woRjj&+1nAVMgU3(}mW#C@)+t=|{w*WozOC%kI7GPr(K?;Bqw~Et$9l(-BJzk+LMG9@^Hq9%p&B{$2#UM$g749e'
    'YN?g$)}5~N1r{`}y8pysA}2l?sQY>jjZqLKO*2#NFXH*!epTXPxY%+x*o;y6kNZTG)GY`MAnRE89J6A^^;`b-lT8pV_gS~~zE~l`'
    'Tjve1Vfj$szo43WK(v}Z4e0sVsKS};!7;vgPsEf=uF_n<kogr%jr@&0T$<0hV-BLvS?7|7_h0YfAoDr}&}Ig^B;r9Wdfb#LbHwlq'
    'bDs=Rgvly}bs8V>@YKWAc#LDu6jq^<ANcE{2ChaqVQ2LM7lQy`-?zBxtJIL5B@h-%?tq5`KJDj4_r{mt|0W1w(l8;}1^=<YP~+&y'
    '&riPp?r+uGvic_6zZZ=dxc~yA;$+)6)D5eC2L4l<6uakv8#hx;)}zifl>u!ePVeaO`2N%pi@~7B+l*d~!^KWuFv+hys`B$pc<FrE'
    '`Kj}Zo5GeCf!<4NB@a`t@hu)pC<{+Oc_7Et=c4ScYsIP5Dr|ZQQyZD17|~PTWZ$JjGyATfLhXn|%@a=;*?ol;@2P#s1r5$WmN+1#'
    'zN%rJ&xRrv{F{ne+Cc8UwslO!j=22=mI+F!=~#d9EP$sAS*ZE&g$S*lkhO_O4Rv{Msz9(hSx&oP1&L$T*tbe)_EfW^_8(k+n>I#q'
    'qw~LY9G}N;0~wW%!^@J5r96C#wHD5m+fgX?>LnLJA}?8k2T7J%MCB9{R$aK-D6K+7@@onAR&AwLV{i+{MvoQ1NTPlzl?=Af8;H9d'
    '&KyrDr%T!C>jh_2#<qB&UCpe`nQ>^4T#o=S%p(6i)IO<?(~EQSG-JcEuec=ivZ%~48XjGPZ%eV1%`(*n^qHSxw;)1T@**x|X-A8k'
    'oYjrkuaaM9Qw;KpdZzV|SIU%6PF>=5j$VrHpAJtmn#E(x=its(5-6mA*-rR}V4a7l%`{iSg|n?o@3D2WkFfryQ<A$RV2ncse~{(J'
    'jbwT>>Z4vv?)1*egwX(^B=D!HL1le#89}2l$cyuv0V7}B`uHi`QBF6ud88m;gu#T&qFk2&C4q5kvRD3$v!eBpBKBJ^0K}vWXS|z?'
    '_cwDbKeDravE0N_=pr}8TRh*<eWDL;QKFXV+0Y6&D?#Sx^N&~()w=+6LpmOOZ(U!_$xa1<_KES1&6!ffl<kG~^U7BJgy2<cC=X)D'
    '4GEvH%InyO<BCk`^pe`Nc2*Ll6?&q(RMH~;`g=Xcj7X%(u<Al`G5VQ`VIP?lCjFfQ<xdQ&q+FikXY)Ayg!X3tx#FFUlUFrxL%nl4'
    'J?LM&o^4&BeG{ryJo>smr3)jlyU8fp3hiDDHkih$zhY7cERa_oLuvpJReKzs6V-qdmBfU$!TP=$<byext?voYFv%Q{A6BYt+`d)1'
    '*gNC8xObELtA2V7H}&(Kyr_gILS-}g;B?jzzyj%<E`F`SXdr&fC0>{7Fb7gjD#iH;5fiqNmip>5F*@+SL%Y*q$Z4%+=NSp%jOM<T'
    '#%?E0zr8mE(zNuDO|n7~pWJ2qNz*3nY<b#rnC47%us)0tb({{HsSD{J&ZC5<B`V+Bw8(4b_);{YFY@rlJrqTYRGMG$CzGhlmdKlE'
    '59_+p0|DEUCy(bp*>?)5XN!EQ|MW=4d|JaU6m7{aN<(6!kJ9iLh)i-(aUmCibMOSGAX}t2?py_uWsPK#{crh{IvI=<W_=6_xwlFY'
    'QWh`AM-_TRKnr35w?>)yKxkPiscb=LhQF$mq3#SHy;OCuqOA?|=o|}Lf9*i*49LqiH>g3Za(MOPII<0njJ&ww&3^1rv=B((mS)qi'
    'vf@Q=&4N&9o{a6j?97}E`VXZ*N2(7k)>c>?kU9Ci(D*OTaRvL%t*1`;hl5_Hj~%7CU=Tg}@1R(&j`o!7wkXjB%gp}_vlBQUM#6vG'
    '-oKGxoNxJ_0bmHi_al*Dhly&M<Zr~yVZ5-er=QQ}6l_;<`0U?oz5X?(tL`x49J2Iq)?ZC^M{v8vBbn_>Hz;3+$!;=~;ady8M||bN'
    'JOb9?NvI~WG<L>AZ|QHKE||-e^|4{(xCh}eDBxv<b~<pNf9J+S0gsEkQ8cK`$3a@_a=DVDREAkQ%fe!?keKM8B>-bKk#yFFdp+#>'
    'TXD41(kAktBW}zai2S&4Lk40J{_NmZl+1Iks0ka4E~u)!&3-Mi^?@Z5Qnhf(uLMc5tlSl&xEfH5XsGkMI#1+~i_C3U-o_eR_ueKX'
    'f%<AE#>s@C0qR7K$m!m(z}1E8{yq02{d!;g8r?6v(5ieg&WXjjyNn>4dd&f?gJQkeGR#p|6Bt_i7GB_p<QdN+HXIt?pY{Fg0BtUI'
    'Ia;eI4uNumY_gM2+-~MHL<~v&J7VzDT)-=Ng8#`@4uj`_3Wt`(N}M_abeTc9+@f|0fEP68=yFLMfATiNBV+M2Xj2C(s~A$$Fo~Mc'
    'nSvF+X5{xlj=qql5<pT{XLD>Dn(A94gCNivM?*Ml7XuKPJ<PiQ0t=ngdhAJQb<kW->eaFB1C^}s<`mV~h*wH9cOk)5ki=Vk0$j*='
    'RF2=y*dnY=kBybGosd}>*5|t?^qcc#2>F0C9l0&(cT&}HH?IA%goR%}Qaq3FxE3eUkrcyS;0mn)o)=Q4nuO1Ae#GP1mXYk~*Y@1{'
    '$U^WQEiKOSfwAT>?0$f22k=0D75@pXqDrc786o{*uh}U{uHy)U`eG|VrkV5KLBGBydnqF3cto_h$i%KGWfS>`IG1R1LP1=EZj5S2'
    'zNXK)_~z<f@)jwf9L1@)15{*yyg6rDUa8}v>#bKA6#=J>p|o6}jp;l#&!>ZmpUV6VSWQhCF21@|p(F57JxF(qGy+AgPJjCsf7ke7'
    'G=`7d&suI~&9`EeO}jlC>DWZ)F8na?5M&s!zpefz-3lorklEWRmDToCJtOdG#@rpIN8h<nGrpMhR)hrpkUzl&t6cV7k$9nng)ttY'
    '?x19)bKUhv=<j17*2*EQZKF}fE8Jmx;uWwFF*YE!@J9lC{ltpA79pNlffbfT+9=@u>8g#ka2f1DVrv$PBl|kn=;_LifdKsq&FB;}'
    '0}s0#*HREAPz%dM&YpS89h)TOFF1uRQZd`pBP-&xcJPa10zKRL*HnK$3CdUEVs4PIPYcv-JE*Cfvf9g%X(dRV%`Ie8y*VpT==VJD'
    '5a`A)xtWjNR5yfZV^#C;$WgT1X3JAr`LyaKSbCwxGNEY&%X7OHlp+WlqFJm1O41}`4t0n_sMDaD1c0t9l_%w^7tOa9I5X-g)3G}Z'
    'hwT+YAN~33Zm(W1?$o9q=dvsEG6LM<u1lJWm4!3*7yqLx8(&vfk6Ng6g5p&5etP@hKp)7I^27Ea{;?8|dipqYuxB-O@Z6fc26VYX'
    'o*S^n?8F=q7W6HV)ey2s6$|EH%-L(4>N#ia|Iz7<==6UXgds34I}&<X^dsgK{(*&ka}B^9-YG1{n)q!qys6>VW7{U-u&n>N8u*;7'
    'hK9ZljLx#c@-06xDq<CFavKO(dh;-a|KpxLsuHC63$?x`g+#j(^MLke@eTK-FwkVpEg46J6NWqwpXE4K$_05DR`UcEW%s3p9c^oW'
    '$=)PL@z)$qkxL_@58PF9yO<2pXuHi0g$38r6txj1O)`U!B&8m9yLl|I@(PYBM9@^37X}CNBJkl#j%)BC08sF_Ds4v%v8DXf7zOxL'
    'R1HsvQFEEDNqzAvvLCzqbJ)jr#<zz5*Ie471{#((<9r2(6fKij_D0}dC7F@$1HyB^;G{$4tayPJp6n?ii4%mPTi;|O%t71dc0n-e'
    ')1n<n?@{Xb_HuPwip(p0zba(@mhbaxQNUb&)42S)N*21dIXo(Z$vHx9klTV(QvKuv3k_G(R*m>^<lvAzR60u!Z>IU<<|nRxqR+6M'
    'h}0L2IZ8sRtFWW+ESd2QT6Q<RS?80!u<h^xt^FO>Qf2ogKT6<7E>V(BX_$*Qz|NZ!$osh|&q_}$h<5$#;M#QG@`H)0IYsCO52e38'
    'ME7YTDTbMKT=Cz!V7Y4;FI7SbT%_9+(j*I?>K<Kyey*mVQDK2rEZZ4&LzenAB_>U=+;tPi;|aYuiHFHRozf_MZmI_Ub*z4!1@a(='
    '$ABX%GtzITFY*aaSa@}2#oU4c>VZEBIWnvuA~73ZgB?!5@1|n3+4&uYTmK%4%p#pYK(90xregW~sZv<f0=bith*Mj_KR(8hS$&R`'
    '4~?ivf$J56BDKv(s^>N#_%1OPOAFwyU}6HHZl~64|0-*=Msakf&h~uPpEy&n?qO9M<-J9~J#2cjGcTXy@7gqVg+%J?L#@TVQr#&f'
    'Qn`>_J?Ru=hZO2Qms6)PGsD#wMk(R7Fh0o-HBo)9B{T%Ni)vbESb?eXe=~zX2tED(3)T0z<J!n(K>((WM0&&$j@Iqk+l01xpZC^f'
    'MdCn@#NnYsghBvp?kG&aS!o112sK&}?0?CA5Uai-O}7Y~Lz)AT*#?;^Y~mL<2V-OdlpVMo!)morSKaY;??O1v-su7a9epd#6i<qy'
    'x$L5vLOwuM)TNk4g-VrO=1jh!;mZz6c)bueX;a4*>XqF*IYdNWwri6Kx_NCHO!auB5p?u|T)vG<AqA&fJ`>Y&w>^hSi2RbjD;bGB'
    'J^gi2_Ep`U=9XgQJ-nO(j=nDM*|2y59oO1UyVub7MoErdB&cw1L((?n@BKut_M&Sgm?a2j(S+#~g^oGOSWUm9e&+@p5Umo(a{Itv'
    'g!pR(&rgquBpzMn-qiecrEu&EcB(w`iT$4$Q+oh#<qUvVrhy#kP<+xmies+BdgEMdp9esE*b!5wx`k$_))I)wC<TWx*~Z!^hMmRm'
    '#9>cO#}xA+BCVf!@kMiE<ygxs+;nL{!*EMp@{w%d;K<B1_gqn|yp+gE+fzLziYW=d0ca(8-S0|Tbl{XLhn%M#CVU@G0kb>FH}vwx'
    '8Z@^_kN84dtYXRuyN22)hj(R9wtE)=4WDZ>%Ma)XN(WfJrhq6f_4@O;EO^QM#?7_zq42f{X;um<i}Jr4TS(uIYk0y6-gi?RO2K21'
    '4k;f0c~0SU)hqQ;KY<a_WfwcbX$@4hIq<!mA^$g0iz3-d`c=OTS(Nt3EMnMSfP2|-&Y*?7_h@`g*)DQp0T;_lc0fdsSfFU{T1O$D'
    ')+mRK)5dn7f#bwoy0AHJS^SayCc{$vm5x~r0Ch07ENOi7_DS>si;v#PsA$*~d1Zo1_y=)!VOV~kX1o<uYoVi^U|vd|XfX@wTB{<X'
    'gFWO%IOd=%Ir>B1)V0vC-xJhB3NKude;}v4ePJ<24Z~gODY|NW)%b3@%GdSJm~1?q3C`!Lx>{ht%m0oxODQ$9Oyc?#&$x8^8bAXZ'
    '0%v{(gVDL^;$o}LMa50LNHb7b4uiIQcz!_Uk7RVz=emnVzeq27O!W@2yTANF_Jqd+XFaO|E>J`cny$%L@w93=Z9FF<46w|PZ2`s@'
    'qa!3MS1(!z@^|eJq?=k2exk8d;JxIH<XPqoU7~$*smb=$-H=VEoIS6||3RkmM;fWxkygC*N?oE2681MqA5hiKLPy?a-SJA+>`*gq'
    '!%((`VMl=!LEpF_PCspXP2WGs&aMz|Z=`mliIxY&79dK#_X~{GY2Dp!6}UvIXJdz@2cS!=jk%cYMO%BH*do&uy|p3G@=vMet}e#^'
    '25|A#wi9Z#IrW2i?^&}3EdOXUhLDq4cEKXwR21%vZRcQpbU;vcB^uSFGM~VFI?XX-GbS@Rj|wSqrC<e{CImr&q><cHq}0y=n3cji'
    'J5b?kZAE}HhZof%&!Hi1W`jsV*qoOpx~@0r-;K-qD!RaA0h3=I(2ltv;hkWp9F4Ara>Wc0cHo#hQXc8{TA=t_j)zXSSuHo48Xf@m'
    '134t8tBdGcIP8sLikckxM_1ZoFeOBno0!X})opj}t^Bg00iO{v@&BKv<%0w+@3^MjinsWS0~sOj+RlwD*o~+Wld-c2l?s}YAETW>'
    'F2zP5#Np}5t<Ue}e7@{;G!ppy|H)nD%=p?oLm?=kWs;~@wv_@5sb_S7@gI#rsfQF>=_P<Wfn*dw?93Y#<&z@mMb8qe_ysRy=OwmN'
    'Leu~WDd^|h+KOJp?UXjn?WSK1cXg5tuL>}qJ&=i`v7<0z<m~%x%<h>4W%tm9XzDg1WA~!Hv1Sii9nj||)2x29_RqH6Qn(QkmDj4M'
    '2uqPev5PqXO{g-ZK&E9dC57ap|Gu|3Qavp{`$|Rq0Sl+%Li8MNtQ-2~=pe}2yO9bhzI&3__g+A{9vm_)<%%-?`N$(Fo$3nUP{a*a'
    '0}|R&UE%#izuQ3%^HH8<=2f`46{%$p(8OlPyEGs+p82P^;;?#!HL>Q(3`+oLv?5F0s5(Y&84a^m^VuWaAVyZhemW`S3kI_`h8JfO'
    ')Y`{ee+X1jpCh$o3GHZ2LBKo#RYL{J>9#rQ8ZiL?uD9`=c6Qv#iezN-Mf9BtWAGAc=VZ5@b*s8sX98GVCCCKi|8<i{KC)_nrb*2d'
    'r#@Amap<vwY66KM;LP7gQ|i_JTpMLMHxc5ZH<Cb%FXvGDj!Oa=sP7LZ2sp!xv$zFnj{PoBzogQDnW^*<aZR5#KvmwEx|_>uZ;PVN'
    'f_f5tR493TJ{T!wSh_VNAI!Nb5_wtJOOrCG{QrY=p#tt=bM%!me!)nC!E=iPMqyrJnlq%J?f+%f$H=<x!h}$C!2-^E19JLpt(S=$'
    'M**ZA0=c&rB=@dGpzE5;%0KJb9Gg8j0f~ygv60v)#T-^|KGJ`HxHS?X_<e4#GxQ~zHvh$kWR%|GPc$R{dpXMIy}UBYcB~8~L$^Ib'
    'ETo_t?hh(f@jX#>jn8-k5hHop0AuC|5@d2(&UA@(e;K4HbBRy3HylgP9c(@zMjIIKf;_{99sBG99s&b{7_t}Amxo2gRatI)P!iyN'
    'c^1K{!L~8I4xiW;v|6p1RtKbrSx1wRyrF4rjgpk;62nzQBQmQyVGjJ4pSi^_!@K(>`*09S0)J$LWVevMp)pY=5VQaYuT>qDPdemq'
    ')qM9oMEcl)=Xbb5r^qV%gcSUEJ;qgN(D2!*{SYtw>dsZure2k1FeeO!sJN+rvDR!DdDIu+z_MgA=piUo$%)a!N3m?a@??pJSh>Qg'
    'Gd7sKN28Y0@n)2N!t^!;{sNy2S-%3%1&LJZRNEh`1)@obG~QDgDKzx)RE7Z5{Sp49R(~RdHj!0Lxhsw-;|>bn(8D**jf^^XC$$ny'
    '#2wz7qmc>r{^=ZP1$muM%O4%fxJq4lQ2Vs<qo=P9o!E3@u5IbjWf$zLV_ICt<AZDR=kvL3E<*{!q0%oXHe=wgVirChCbb0t4AwGG'
    'Srsw@z1E)L-&p5%kQMyoi0soYzw_(eaK*sdT@`S^@-Ffe{g>RoQ^K00{~kV+Z`MT+fmO*0Qi@0WwqXHfa3yqr!NHIpJP6Je)>jCA'
    '&Jn*6I=DjIYV!ODf}tzKns~YHYh83GBV1&U*59+B3~93z_JMxZANHj`le^tXIR3ksMCpH0(l2UbY=r>=rmii9_JO{N1@*@z+MY=~'
    'ee-F(49(!2?{2e4!MT+}{7VnX7i4znZ6FPT&GYHCkGLNNkY*Nl1P}qzyScTK+0U&Ny7)v_UIHR10lepPcN<t<^_(lN>SsHY93WX+'
    'M*hCGdf|Xs*l@{=RF5e1X9&qo2bq_O^*=BeW}ePgzc(My<Ib|rPE36W@!FFJ9R0Y1^yfVPoL^x*Z#JPNQ9G@thI8d&RpTc61o6C7'
    'U=Y)P(jkS%DsC$K=_8_~sh*|JXyfQZTttiCf~oF@gIP^qwi=|6DP7j09ed=tNJEnV@+4AZ*Qh;&1Y%XB?2q|fT?5<=72rgoY88hq'
    '24|btfQ*d{+sq{|Fo{=*1bGL~Uk{raA*=3i@>(Mqku_dlk_WqGvjJ`LgZcPqtn%``N%Q51KyG_g9&*=yDVtcwNN&KG<qV3G`58=t'
    'DSDgN_V-6qt6uQXjekmE(nbXfMn%aHiF6f#D7S-k!Z=O4-A2j~hd1maa%OD$=Ai+i^tQ~GahW<1J)rO(NwZ62A^%UQPs4*hk*o~^'
    'nt;!!RPtAx-w_=47)nj{)rY}Y0yus3f|)QU%ri=ixvj}0-*pXz)OH1?+EX+8n1w6l!)YpVe~8mMG&m-&;AoEJ<4}?LeKtmg!`Y}M'
    'RCy`zk6_4#vTmsoO`{qHN$aSgK${r*H-r%aC@ApgH#$H>5sFl=Dd%E==R)ZM{-H?;7)&vfJCAYwtU#83jq=aFP(>{gBLiDKdZ3*e'
    '!;L+f^F;h&9Bgi(4l@oY6T)+T;D5wM1aFXqv~2&$284~EIo2hf@&n)aACqa}D|~s%{KNsM;Tey9j{w{9Hks^%q95C4Py*djuB6G8'
    'q0gG#s4BamzobdPHFhP7x+9RmQ1c&Bqt=g1sEgO%L6-`3?AkseV<fTlVM>LR*R$!QlH>-cqr8nWa=-lc>JCwIz5)}Cv&8`X|Lr~G'
    '851*BHY<b-wYJUIA+bQ&Rx;Neab1$IbM2`kpkn7`2>c~DPif|P<r)X?o|t5dxci{n!||w<1=x&hgi)kK`;C|TwlMAv;DGuW0Im2<'
    'T|!GO1q@<-AS=RU9mZRk9I;4Y0R$xf*3BLuZ$OB+nZs7uI=Ou(^?%6-_XXtihrp5;4h~42;fmKNS=u?47alXVT`a#fWOXy7wVFk+'
    '=RyM%<$>W$d1+cn@?Q(&e@tfn%5lG!7%1YaS*L5(>3`D4vN}%e(nVmF*_FAJqzqqV-LWQhh(gbaJ{VLom2;%&;WR$@)J$jE6!|9P'
    '&z#(>N3Ga1rKtHrALzMpLJdG;WJ2La{;pXpSX)29g~$<_FYu#z$&(5q^^w*D!rrGkV)zW?Qw#7%&QtYmP-ke~){ra=n)ux*<=>=-'
    'J_D)G<^QtW0k~{=Q8$@-4a2n#2z6GU>Bg7It&40EU1$VrJkNN1p5Rf~wYc5=1u<nvIf2V(xEN|3Jgb3l+U*PebtIr;Awxt%n1k`m'
    'UKK0pK_^d6|I0I%gxgQc(PM>C=!(Q4PZ670j!hAX7l7ZUh*~Wwl}D9Y`pm|?hsrl8Sofl}uB<uZ{azb5$j)U0gP^MWn?Z~d5EZsj'
    ';#}V$-P!|Y)^`G=hg;pE?A+n5t0lK)f?jQ*S=0v`G4<%b;?SP@nxf8zAtRZU@Ev2xz^v&))jzG=5;d40WZa7_HzRm*{bIfc0_P99'
    '&ZQYkA1BoFk1pt|xC>0&=il6VHAQWAUJ}Orhohv)X0?3N)uwg(&zEHsCBUV;Yr!|yo+@7b2)<#WuXDOSQ&{dsh&eD%*3WobRrtwI'
    '!-E$dUVX*!RPT0!JZcf-`*M_2G8A`2!q<U1S-ECJVkss_uq?cd<ng4)qkbx+QNe*$$j-_d9=F54<D#HRMWsOtZ0)x*tdAL6!K=*D'
    '`YbPFZKn|j12fFff<ZCED7%eBUzT~I@Cr}06{8?y#x_oC7U(<N<1fEm06p5-6@KT<ciZEawi$)`9Uk5SLOO!Co^nNl81_Wa|2VqN'
    'k^U6sl+W$B&+@1Z`%*xoQ;FnS6C3P@5NM$<vdh5sNIti%_;=tB&vT%Z@ONhNIV}h&+D5jMOj@257nDzhi5rJc>p>PJH(FA*>4z3b'
    'LsvHrsot|*d$3nPVzw0;baxnD*FE0GQl4cWGi3NdH<&TI0^hhix6#ID{>OMsNOiWJXjm>K09U#)95iUwW)3qDYtdNk*s1T8wXz`c'
    'rkfR1sQV5=-e?!2zEk={+M$z`3*B|%dWY6+Z%`wo`U=;%Ux;e&@w8Y`phS`z&-Dyf?kNRVU7Y$8WbJDA!idu7TJa!uLJCX6Bu9!H'
    '`m`~lQMg&ASxN#r)Kjww7{ToNinz(c&!$vqU@KTv0m*qX54!^fjQxS|(}+~MQa-o*nx!6r)YFXg5J6^8yqrAx_5RYpa?^Zc=}zLZ'
    'a4PqoKt;fYJ1!Ks+d%)T_DSjCL+%={Fa-zlwyg84Mwq;^K;e|QnSVJgQvCJlAtQ{uX&iMHd#!-pBqAlc66%T~v?rIP^5E%nI@m;1'
    'azrp*D=lLmiaM2p2GzOn0X9{)D&`7(!$K;L0%zkHs2y-g98M|wCcVYePFj;Fk0JiA!|J7Sf()3pnww$inR$g=2Xkjeo3d9y;kHvn'
    'k{=R9#h_%pg-J{Qg6A4h_sJ5?m7aBUR323YwD?Y{v#9_@t|7<Lu3w5*+-Lz-ay}sJFKW}7&JWIPNVSvtb~BcXIA(G}?0s;>$UYMh'
    'zh=3r90*W(dq-O^X`6?fE#H8m946Y+%MOhfN;V;}?_P^gN7C-jebZ|L$p4Jw>G+D=xvEv`nss_nNRfOv^<hN%B_#aigvEHm%?dB?'
    '&u?PrsuzN1pqr*aK4&}^S#mn%A4oKlt$^yIL_<q$iWc1^M~r!>)0G~qg!PUx*gfKC3#REmGL<fwaLN0lMx@KHzyB6a5BEsZN#V%-'
    'UJEBVH83X;thbOB{tn?XXP26gH_0zdJN2JefJ{5{T?bd5q8}okbnz`5w17}5gH8ZLbB}u|F$Zt856!+2-d@$k`&=WKpou$fC!M4M'
    '(v?nTDDBt#;uu}#qu#}4uX>Jb5-o~DztCTBgp-3aTq%=aVOpBeN~}HiJr%UW=zx>!rhbp#+skl4wvP>ZV(!ddF2NKKpJx!FLJb>3'
    '?j8S~%oc>L8F;_!YaZx^S^}gN>m|qja$5l=ohf@5b7Ji!>><3r|3vO)gKWBYynAy0+{87uxH`-zN3(%-k?%*4S5G1qC0I$jZ_aL9'
    '2XU9O5<E66E^nvyg*p~hf8@7U8ED~ha06)&hq_cgFr#k#x;Y4tB;?l5fs;Y|By`(lZb7b($CJlw(?M}Qo;i4U<?E>#59~a{y2ydM'
    '#;*G_PO7nOG%LuypTM5!e>@#5XRaZ{;jpzc!abLIt_KIrnwJpcA3u>AcW%suVY20rU8tqrih2_Cfjs@<uN#%oo4FES@Xf1X4ZfH)'
    '%vvjaKq3?9@s2HLyBCrZEP!^Cv<wsJYU0WdUwISvGv1kD+fJOJcY|H;wt!>TwIH$g`Jz@;^gq8@=~zL;X#~Dd>%U9NYCK*&%_I^E'
    '7(3kSG^w&u0+PP*MPPC7F-#4Dc7T~tGHnElSzS)#AOgoZ{KL|KQ%`{h<}`t>qIjAPe!MEcPc0!9A_$3O$s51KVqfacZD_DKNwzQ6'
    ')rzYR0CPfo$x56mtc@NiKa_n-oNuvato;@K*@uylgyzPL<pjLlf*KkLu!K7Tda^|zAA-3!W;tD9q+Xyq$NnM7*LLV?i${#u8lxw1'
    '8a}a`B<~h6_&svJ`T`ImPmcV#Bsjge=PmBX*kkW+F;aaZh(sX>NC)Jzfr@cCpx~C<1;nyC^^^2>gj16oi&{Co)PQ!W?$Ah3WVbCv'
    'AS~qAD3m|FL_15AVW?GNfG!f3&xg4hO-Zg*>!d6K0GpP(RZ;hs+E_ZlHc)3rj9Z7DZJv+_0ev1F7F(jZD?~%77+2<Q7J2$_40S4u'
    '(>y%DL9YvIx+YtAa=nifjgm<Az$fJ%k=Uf%F@Y{psnFOai+6aNirAM9GZ~!0G<3SaDTnUkdHD=7c@lOd(8UY6!$)ar!YhOfG+$*9'
    'PZRg{?*gTbgM~}80|)Su->1>4R__>TtW$eYq|$=kc{=Q~{|$1kTa=-NvOqo@{5ho;y(O7IhbwL#)}HResTd~$J+(GGt8VH?aS6GZ'
    'roV|pSahHdwXCrvGi=Ye5vO&0xr_4hkT3?wr`AXj8D-~(1cTgTW&YMt@;Q@cnd<rHC@#^Qc6p(u#vOt^u@`HP`a8yKiH=UFHIkfE'
    'hbqaI$gthEMv1X<kX^E{p~Pgs5T}(YlT?WIBl-7_-eWC*3g;r(g8=Bh$y{<WSI|{}=cT@aRP&VI#vX^O`~k?~<Cu6HQ7!6*9$Nao'
    'qZp#xil=^^5T`mwtm=LR2lIXYi7ToYbq9xF6C7C`p1w-be82%k^BE6y8aG>JGrZ%jp<&)N7+;=syo`&hnM{<vuY2unPhMJ$kTNXy'
    'kQ}X#IE_t&4ZK;*o_#;!x~X5HJBZfTV67+3LF5(wZmReBU=+-~Hi6GLjYxFn$j>AxU@lY<4Y@p;j5bZ_+}9qp12-E)w=VzQoxQ!~'
    '7PR;0_vniuld-T_9nAG>r9&mUTqQQ2xZTE>(w%<8>|LoyoolgxZ$k-f`Zv|ig%(OW>Bx2_xk06hg@XsCTDSQa?BT#giUjl41@yFg'
    'IRqEIZ2?@m--TnBtsxL*a;FF=M&cyhaa2G!KsTM+sXggxzTawi(sKgaVeT<Y)H<A9f^GmTO>z73Sz3T7QfwDeV=p4Ct15Shmc;Cc'
    '(C?iQsz0Z%UwQ4&o-6mSC<D{#C(Pp}0j3J8;=`<PJLw$Ak<alXv-sv9r(1YQ%~W|`V8H9ov}!m=nfDe7tPvq7fAf}RyRHKy2Q$1T'
    'k~#u{m;j4Ayx)@=BHVNIsrlS`M@z@35lVSs7i=*!Vbr_q_KXc0W2lYV16s%F?{+qau#5Rl_$la!jZ?RinSaJ{ITNU6D$D10wx8!k'
    'PPKmemg$xA<Z<(rbYycO?>vWgu6)6s)K}0@uli0bp-(%Z=w`KL1_M#{LYL5I&dD21Jjb%!%ZcD=l@zOTdFUr(n&-XKMnlaJ8tRj9'
    '0UWg<(=4!f>?MeeR6VbjQ^xxdFJiHrOy;RfrbP_ryyW1#2VBgpEfu2R<<~y`Q@AaC{l%ppj!hn%pJy=L8bqD0l*oIKz$Si0f;u3|'
    'e*hEX@ox*_+Wj8!pd8%P;L!mbaF9Q@6mUQ(r~zeXoi}bmwMWbegDL|s`X9!(KGB0De49J0g-r4BVI=ti1T-+)g5~Di3cx_`f}%dy'
    'I_KLj*2IXXK?E|Ae)-yl6^b}9#K8cSLp<gJ!0}Y&0Iaw>CT8#08a>y8;%-`iyK<W$=P3WF+u4XD3?dNk5=}bp57oea!t;IP(q*nh'
    'AR}*vZD8C|BihyWy}eOGwvk;|d=rb|WjkoVJ75w5z`RL-2t)0RGIb3}$a6wK?-Tzjftm%Cj}p(MfO?~MmmlVf(*FxH1GfPXXFc`<'
    '|AQuNN+i=o3jPIf7&?O?3-*=EHaIp<lU;6(DKLd38!ON8#&b`)D<~8aImv1+wwfnt0tKod-hzzk460k`jxrbbBAaFqb}C-3l+OMG'
    '04W6B9%+wR%qbP!IEKgK$zS&}-}J7CTN%gtE|e*9zU*i-gyOL_Xmas$`j7j&8j&{WzDT}|_b=snMXq!ku$uqLff&2T=eu#{?tU=F'
    'LhoIH6tvR!j93|6{A=){woM-kVSwL<a*t`fBnz9Id6{+*lpVOx>b~rV*_ub1$FXP_enph*N!DlE+1mSE+&ms#yRzu&SZUsd1J<i&'
    'lpP&9P3mHZ<e4W#vdXXcknl8XMZ4iT2hS(s@#n)T4meYz**S^Dl}Pq#ml3RPk`|s*aQ2}DYfS?$$6}hV)?{`0y2h!s^g9hM{ixT`'
    'nx~tW!kZE2<6k<d7i=P&kr0ScSn=Z<?jHZ9-5LR*9z(tcEYw319JX*rVXF5Yg^h6sgd6oY5G;e^-!X~u5nKigej--L-9A~RVVU3>'
    '#vryd;v}?+B>EM1fhFH~T7t*rXmo81Y>CC(@^rCEL`K>UzHPoV(>8}UPvp^0Cf?_*>Ii$pIUD@xDDzxc0$}S~q8O_9ELhbaT~@m1'
    'qq2##NCT17sm7U$tLV?y%Az{FmtY`kq8_WtcnUtKloEzO1?<cuuQXD~{i|TJEa5awIGNId;fh%f5L>GyH4LNSdGon^{xg5@4pb2>'
    '5%Mm$m7YyP(BuHd$~Rfz)?S2RLT~s0tJ4$%=x0))L>Tnn<}&xDVW&aTa!4FL9yw&pOdjQOjkammWh3U>ILpwnd}`s_bU-9F2uj_;'
    '1XKTPG|R&R_{BXW;D!vqKE{fE>fubn!F`3?X_{Xir)-qd`*9=rU6i9cnC`G7dtxwio$nr!kx_4fJO_Iw+65OM5pCjE4CjJ8phnny'
    '3X<jm$9Z2B6FfgzYn+76OlXzm3k%Wwvj_Srx{HJ8a_Uda;j|U9^QWckWtENcPqco6O(o`eH73%rxQb8^(&4z{(V66G=x5tb4g)9A'
    'a5;uWTSkxQu1nEgB*TE!=kg544AA|ohv1p&i4A8dKe<0UU8-U_{nz$TS7<>Vuz&}eFY%gW8?g0Q?TMiRq9GfLCznC*4Byi;6i$bb'
    'Dw4CpVV9%NvKdDg*MV?!Wt!vL(4=hQUaW@<sb``i9SusoYYiqy)MN5Q@nmg75svlk7<2&k2l27<mTAKXD>!><&fpO#{M8Uq9ppg;'
    'yR)h=y<*W3de~U3dtdR|keDjAwN=gq1@xhk0+U>orG5$;kaP4=mv4BU;6v*-Rono71;aEM=#4=vq3hG3T#gFxJ56qFW&B6Gn)np$'
    '9u$#C*#W~R#rp8QEqM@w{W4?uJhGx);bZX$Nr>dSM+4jz{`-sB-#+bWh8RdclCcsv&MfYl*l8%wgsnRHUrmafMXo1(s5(CLM=>8o'
    'sql2$eII>j?hJwWBt0JhIFUzU=wMeC9yD09o~$!Sp!)YJue(si%C4A3GwP<~E;n4dEant3nvBqq(2{pTD0fAn_|BnfW$Y25XV@aY'
    '5GeC!AJ>Y6@NL;M<-#gyc&VuWh*}OMDlE`@-x(@VNiOm@eKS6YMS9csMIfX2!fTc4^S7yNA0IrEotp8w4^@n?u~_}=&=A+H?AAd>'
    '9?Zm#2ii^cV*=PaG0;mT5^_8qMG#NGG6`j~8N>_OYNEtUG>$;_jEr_Y?alh?f1K)SB$O1nR@6BwotuoR@NGDO6UTZ}1Z|?c!wioL'
    'GTp(IiWzvc-)uccKE^qZP?G{&Vjkm6l-_<1{2&93)Nh-mD(CO+hC_68SO*+$u-R0ec;(*69BKOjX7x)-=75077sN4p=Y^P!x4`!E'
    'rG#~>J2M?*n6qmE9e_hIU6?lXgc@boPb8~|eD}TmG|X=oIHQHI0pWKdtAbw-$>l1)!VWqu?{BH2409+%iPsTZfEI{h5Gj^9-6S*F'
    'GOzLqe|oad?GBRkk-*QhfQ;qZ^s`yc5sOAp+CeLreV~%1i+snslDWz}s@N@M7ctmT?13uvFd>J>0=9#xe0?6%mfwpPnGg7tB{_t2'
    'K_{!BU<0-iE-Wk>z=N5Js(w%4`E;{Rh|Bi}a&dX#<rkA_F#e*XkzgwWtsXXVkxvVLb&i%RS+34hzL&zthmXO0hx!2*YVdFkbXtC}'
    'PgPZ9Se)S3IAnv>wB6+nv2-YiyzZa3#vV7$aB{7%J*`HT6i#O5B*Dx&AFoFFQsxd&XW0RT(RD|1^4Dk!4)^^kDmPRvEi;a2V09~&'
    '$BT$4b3i{^L-#{6=BKDn(e~>#axh-!{BL$hZq?0!@$mLy(oQ0%YupBKDhXb4M3j3s%%^=?r-NjPN6kQ_+m^NWe)%?GtRZqClb=g@'
    'k;v%<!N{ce%&%TbY*@jzyQT+9T$S^-zlo(MHsBjmVt$tWUNtwi*jBEtyfvKHLgl^!Ry(<+{Xwuz?~rq3_<um2P~KAzufBfZ?924a'
    '@cYsFn@v9`u#ha+Ay9vt7h1qRzS$6dZj7$e)X@cuoe1ngWhAE%7n`Z{iOyIZx&sWi+KSAyze!~JJ)u^mS-+{BRLS?(%+XJOVO@!7'
    'oq1{$wmiY}s1m-r3o?QeEM_Wzq&g-$%sK7u<*sbgP<|Rrr3E|pBKEdbJL;@D=E3isuG#kw%ysb+Zc05_!rPKb>R%I~Lnp05r)UET'
    'FzqeIGr=*KydgCqV(P8$F3m!vzU~`8nfb5xqNX<}SVL;U4~}jwt~agDS9QH!+$k?JdH6{Q&OFQt@7`0Jz+aS!mA0JxWp;-Irss9F'
    'kBKDo;R`(t)C)rqwy-G<W;@$U-3>MDd9|7@n`@R=$Ds-am)B@i@mFE)W0nAAJDh)sXa!)iQ<Uk~PJNdG4R=b{7Iq3p;;p97x(;cw'
    'CU3E(5O!$Fgay#=vv8Fp16ilnfdlKBZPmD=<=hb6&z;E*dkn?<)=KIGDz%i?!!%;zOgILK8N<NJ(~<$l{r<oLUzE{`*eGLe0*0o6'
    'OVV#@NBO|n&Nm?F9Tw*c(84Q<t92<Eu{$;pSF3tPiO}-SZjdqo<wZNCx77TOmu#A>lMB!t$a!2ws<3;3@pnijAzh41+u%O=BU{{#'
    'w=TkFO+~LEQFX^g62{YlsDzs6l5xsBm_{glH*Dbc2a>mYzSD5c5IazEKkmyRYkmngwl#-8BwO~M#Pm@&d%uHcaMmq_Xp6Y{Q24eD'
    'Rm3gDyBY4&PwBPXH`O{g1I`2tjQyagrZZGZ(HBS7IQXb^<rHQAqzh#PUD?y^mQnMBVduAOOiv>j6~SvX9@0`dA!`y~s4^aV8;w?E'
    'I{i7yN!y$e`328L0}{l8VJzN`=ek`}?tzq^tc!Y|mJqnhZY_1Kh}$8u*Mq?|`IjqV&(g-EhwQGW*b!D#NlIKr&x}YkvPAO(5h*1q'
    '7s+CT(@dh;M$2bMI`%srD|D(HVY^<j2Ya`?m-y_S^y9;@8fSr>De-)L5i(#vgL8_+@VvACk*Xs9R;Cnb;~rg*Tv3W&pebs(jehRw'
    '4z<{=3IP>)In5zWVqk1=uTTFWfIQo&HsR6}OuD^UPhxpY2$0Z(B8^=a;))BssbJx02#=(NUF!5VSu;_(E<;;b5_C~(hf_nrT=+UR'
    '8JQ_l!Z@hl5TrlQ6<7nqr32ID<@IO+fq}Fv<l;%tQeZEF{g|QS&^vQ}decY9WX_MRT6SjAJSS;CW?f8j8Uc$W9o0}#qnHbc(NsBs'
    'YQcBBtBFc3Ix+u5@q1y!g5Fb_!yRlxKP@kwSXbYitNET?F_lXXwVS*-_P+X=&nr2glr&mz$>mY4#0DGpOX+<&n|rLmNHW7iTKMPq'
    '0UUXC=$3=zeAk*du_S{D3&dLJ$M6lgbXxM7o=b9zmDaTgZw~SQsMg}qgUoX>H2mG|UXW*^){q(Y<d3ule7rCv<YDgs0G58EG3847'
    'k34CbVLgY0KE(~vUr95%yyvCn|HvcI5NaqWoyxUTgXfZZ1UAC4{5%usp+c`>tjjxBv4YvaeaC$lM2T1kb83GP{rb8$6wHw=*rpMy'
    '{>Wb8&C@;#f~0M4nThAcp^^r;@ppJtr-}l_!4&;7$X*tN{i@En&<3r(NYtM+K3d<POu+2>8e1=yRZZ|aC7V3h%q=Qz=bh##)jflD'
    '2mbQ%r&#nywllW3`$urQS~YiPCEeIZ{sL^4Oq^p3lVE-gTQT(uv3P}Q?bd}nN;6l!T4alO0<t4xs<R+YHOz>M!OsRP!Kf1OzpVX@'
    'pbwvycAOIo1>;|=$%Ud?mHvYc=5A~~<2)bisp7HrO7J&ZC8?{I-+3!BNhv)F^?<hBpPwMicFa7Et+&@&>YNVD7x``GF*v*A8N|(&'
    'Oj9iW@LZDmU@k8D611*NN?iwQid|dV8PvqVer?e0Fns|?k3-+v*sF;nogNYyO1Fa!T!Uz(E%c1^cRnzUSJ7F-l5rs>CUP(L^x!AK'
    'Ur5)-gVYV3QYn34S4zPiXG7R}oUod&_U8wEjH~L2qx6rDgi{2-)X_xrfBx;aUW}fSFCrYCKmjqOw(rv3&we4TD5I`xufgi15!Q(;'
    'RW10QZiXwu(6i?7Du_p^))BMm4FdG!Acg+|VxV%eQ84SMXW3LzNMP+H1zIi;>n;+>@jtH94AG6M@&Es}L#--qcubSP)U1=vn{Le%'
    't?H-6y{(Y~;A;r6m$PpEV7WnvBX3{t`GSxu#HT#z#=D;j{3i{51Wgw4_^;AGSMv(s)?@0%0}3d6=c*p}h-E~O^)p*~F$Jtzm+(ii'
    'T(yS(-#W{|XWa{|&Dp7-uGAZI&2$PEo@7qNiR%_MAYsNa<|^<PoB{dA`V8CF8Q-u+TuIaHTJYYN?ZBW#pj^Qy`jKg-Q0%R2bl?PG'
    'tW}>b)ox_#cBs7?^!r5EfXLATb)uQG+%0R`>8E=={$)(L`h}h?1P51?V`@3Og<vzwI*g-jN0L2Ylt{4hY~=LmrV}|CZd%t|J!Y<>'
    'B`vcz_TULejCZnPeSJh!$sXJo5lK!g;;GOeZ9dD9Kr9QBKw5!vp^NTd^hY`so1_zo(FNO`x+zrk8yz7}B<jU9!P!mDaxoH?mOig_'
    '!2V8kXPI&r7<z7z@C;0KTVba)@8bJ6HHkfuY1pugZrxuVHf1xR_c$I8?pO;he09BWvXW?vY^E$UQ&o<giw#iytQ88|VYcAie~W8y'
    'z~XnEf>J7x*lbd@*6_3W8Ss<_YlG9O*sbc9o`#3}(--bylx*npctJw|@-@r7CgbpzKrs^)2Qf~J;`)$P<xBZb@VrDiH^N-k(_lT?'
    'YQ#eyEhHC4I#%%6i;7&*KPLcE2)sXWp^5?$&F4~x%V1&U4iapVygN!K`8Lg@R~~USiykKAU@WP-2Yd<qK(N$-lKtmRBWK*g!Zbug'
    '0943%K=066&({||HpntVMQK|41(2mC8?hlnkU_xnE)BzU*HP>^0$H}tcPD%)ebR3SNitWK{8@|AyWF(s3{@A(083POPx~C(RYfXf'
    'y0%Hh+nlVVlRH2Qu`BVE1H*;Bn*^s?rtnkZXEfw@CC~pVj0MKxu|^qm1kt%5FsKJ_<r<P2g_Iw;x-lhm{tR{p0Cm5*bs>#8UVhEK'
    'IeA72FuV`W!?O(HH&l=XA9{WWFu@k&2h8yXWyPT+RZBfbO^y(9_OjB?&i^e}9Ry?Pk`#ZvL`$y`0YL7&z#zt$e#5gkL2tY$c^vQ?'
    '<Yw+k=3T?o;<HBRiY02|QJf!&-{zzaXq|3ln)xIG*K5zS@}giCh5JAjE4o-&VUOo6L!$1W&=cPtWQHaj|DLHwNUCYnL0Qf5j?;ku'
    'gq6gRA|y`ceK25NJ=1}5+rt{%=cab=SFzuS*~b2;b;<BXo~~X|*++;~av*ydq1C@nk*lxs|1>OS2ju123YP`uJ8mm}{YJ1<UTflS'
    '?|>+sb`>dYfH%GZA2j?Pdm%UJ??=|sVW8g0Tb7y7@3gW)B|>>ib|UW2d_z>d)a>{((s{N!Y9o?gg5<?2o;OjxD7oV&kq>FfxM-o3'
    'Dz`0(eBBM%SNa>fiqmIGbhJf^yD`axg=igNU?KHPF{MCA^&2n>@6O=SB;OL&#;^xly1!Q)zumafH5fw#rTeKiy@`L*s>Eyclx?zw'
    'xMJ4${slc<e(=8sso7u*u(Y9VyICI(l}OcnPU1{#{=O|kmn&G(#Brt2T~V+NYx6fN@~-dRqhg*3b`5P7k_>MJ8ha4sjJx+3d!H^k'
    '@1F;qhD-&*pCbNsTW#M;4RRryR&y#n3_q&H<-R41UjQ{=K0baifS2F590y(W+P(~jRL<&HB%)e^0wuj};6?uB&Vvc|Bnn(xE;B0)'
    '(RdyP2)lQ?^bS)+_)9=A`c2gJ@&r9hxYOWlvtr&&CPyoCNKJXt(6S-AVk{Z(?V#Ufm~{LaG0WlSkBW|(OPuv_GSVmLwe#S-230g*'
    'pQW6YN~{=Gwgh`Si<)?fG>Q~g-*a>o5TSGaA8)*^qzuUfZS6L%S;tB%6J(q5yK)Fp-KbY<z8I6$OwRC+wyPiZyS~Us$qnW=(XP8F'
    'RDjX9Ka?A#;2vow04`6eTJZH+_~N(D8#Ty@q-+DSoA~~9$%nH9y7@|o`G|n)g97gk$B4{PNnf|M2&Gw5&M_=h2&pGWjnbk079&Dg'
    'Q)XHW>XHNL688IjK0h1=$W;Kk+9Y;k)0@Z!k<%=q!e$FoQx-Hhn4?Ib_$0`)Vis|Opr1@Iv#>cMf5t)Ok}>KQcZ)E+AHyt|ML0;Y'
    '^34X04Xs3?O^SF}h_JFY?9e+}LZ-UDEq0JgwG6~BUb_Fp!MuGa1*f|cO9M#2-xY9gJ(&V5K;uE(f-Jvt>09mB5-l6VEC5p<VL*T@'
    'd*u2LygZa!_29BmdBTpYxjE>mon5c7IzC*~V>^I+uM<)|<Q$qZI$O)EBS0{hD7FT#g-B+w+^KeqR0Pamtf6!$2MS@f90C%n2=MxD'
    'u7jn5bYAk!*$M+SbS%bU_*3MJ=N0Qe)+5FY8Lg6-F~X!1&yv~8rD3EKJQE1x2Kjg)PM(r;)}5@$F{pMT=Pm%RH>0OsFWjmkQk{0<'
    'o=B=6{53n@9qYjc8M|0*<0+0i(|*vAY2ORfd`5Gy6YR7hOkP^SLNBF!s{HY}SGeT3hG?aIUxC>2Gr0xudlKk=%|XWJ|FOqT+}!&_'
    '^tJt!Rb<K4O6SJc09e>tf5Nvzt;%#M>-d?`VM3eS)(=#6YZrh5`#s<UDy+|3)d6WjL2pNSpj{^GrN#51A`6T>%4{ytkE__Mij8+V'
    'KduY)sZ|RCsQAY?E5;S!Z_VRMLl{LC%-+-SD6-#7+%1XoHYYHbY3KL(VL@ud&<b`tJn`@NihSlcroxk^ICGa=TUvuv^r<9$12|m('
    'yg0vsvTbGJ^_jNqbPZe{5aTviGj+mvmo~@v5LDo|y!!2P_igD;^$^?XY%V7^L#FWW0NV#A_Y0|>zH_zJV5rN!lK=J#9JR-@6Q&k6'
    '$SFsyU$lD1L_`=R$xNlg?e;0$Wh-JOI`$GAR~CW~qPa>LBRm+U2&g|cpY9Q;Td4890%&CPa4*M(mDAR7ZnWqf;RtciiNR%0MXQuy'
    'jI`Qb_+ZAKHkr@~YU0cW9*kI_&Nnnj+3<>6WOc;@IPRkEE--b8`GJ>Ie-o|r5G5XAtI#wJr}L~vOgbryqHy3*$Rb5Ro|l?FCR6jh'
    'fag^~hXWxH(dD!BQ6-01BQTZocBp=G;BPmt&b(z8h*A<dYxP!u@|$*zYFgFb(r8N$>!eus2Iqip1D{%3Vxj>h|75ym)x#x}V?>o='
    'BZhltMu|FbEdiVZ_by!l>O175#Fk82ga{Yg4ORB6R2&QK1SD#&Qyx+sWD~#tp+m@RQ?~`mS#u>3i%r-pDX|e!&x{S98fKHBNb~Ry'
    'x&;P~COea{960bw6lni8871P}D!Hc%adcwr7^TGh;Zl2cun);BYRyRvIxkyRVpjwW*~E7`4fA_$)O(%yLhM67$_!bnW=VqJ(px1l'
    '_a3uds$f>PcFo8c9K9In?2*zN76I?KNNy#)SkW=cqQoc!oQtAU<A1NEcm{E+nX>6a0@Azvm{=Y8s{#;i;M~ZTLY$WHCizy!eK$4M'
    'szXSFBxrNu(dLR(>dm1@LwI5i-8SA&$4{Tz!WoVmYi*Vnf~XVhaNtSBQ$P`9#Rgdzj<^0zwMlSON=i_2jh`BBP?!<|9Q+#$#Zxf<'
    'sM$N&e)yVm>>U=Ch>br@^l?Kq0RVM9LncA~q4@GoFq2G0yAAA*0+iZm&UqZ}TX<jnua&dW<0-Wq3==|I##+U3U@>_3l=n{H=2Ngn'
    '*I$kb{f`z;O77xJNaq4D^O=K>QXq!rCG;qy-J^$|a`?SvkSwJe=Cxw^e$BnAh;cjKJ?fjUp*s<1-MsE|L{wh`V`d*@w=i@_pUs%!'
    '^kayyLgxtS^Wi^w>s>LwOH`kWm)V=DxWL?G<C^^))y5d^oEv6cB(2u2hPH_ScaS6j(>ztH5gPK7JvTnn&Fc~<wYGO}Q;}f(0Viu}'
    '_e1mVLG{m4E95cA;4?!0NU-f`KvBVejt{^)l4Sp{h3yKTGc81K<-ncr_UIKCth!X!tjSiO5Nqa$vip}Ek8k~-w_0>r8p^_pf0y(^'
    'Va9_#y(g(GJJ%#Q$`JGL(Pc&4aDtNx?RVyIWDpxLl!7WYU6`}9@TH#5El7S<h2w@}zwW+OakC@Ioh8B%>a6Dr2+!7O?xP<7<#?88'
    'g~%Z1tt=jv;Sr)NKbj*Z2Uugf2iZVB%V{1s>0@!)@i!5D;F1lHiI`Y(F)~?vziVU$CXn>#z>2BY5Tjse%lV+ZBdrt5Pu6c2eYTY&'
    'kc(E<v(X$WJaXpqP*W0-Da&+x9i0~RnU>~1LloK`)ALUpe%Y>uN*k@F@6Ex7&Ri_#g#cFd?qum`ll<VVY8zHH7z|V9I{H1q*$6ws'
    'IB_eR->HGwEDG5TWQzxd_uKdw@j_Tm1h~&Wjw@FgG{l`v7KrdO-Em?NE{@b1Qw}n5$f>->YJ6pv`6SkiL}EZ>C&QSMN^x;W9mvdb'
    'mzl+xWk`zYV~F5y?VHI&G((;t^JE7Cl>uL20WbdGM$9jjDZ6)JkKamYs*vl9A}p}So5byElA-Z6`J=~F&EW7BT<^h|kTnF?_Cp-n'
    'Ql2XE(lNt3H&60+!OS^*h#~k8IRB9a(bp1stbp=4frt=7L}>NU42;X<27L^Rhfdc?)ZN(8353|E>nz_W&$Rd1QS%MuK#e_gNsjbL'
    '=-wrUtYXzogp7CYQhf>7v9gmFAW&^*XY@>#LGH!nR)6|KETy2x+F{ZsjwI(9YD6K=DZjp-^bAs#wf<y{i8{H%rPBG-c%EtXsYT@D'
    '-QR~g=Hk`F>_`4jMp|$JQmDjUg15v=)gohFG(hmnX!;(=tT#lDKW6@98!NDY+Aqk}I2M`HpSdze{F7EU4Q7WlSoc5BS1TmX&91gh'
    '2-u%=I^?@H3#2N4WOH7`l{{QLqB%T4>^B(K^SSOfA8qw(OZ&MVs1-~hVr-okNz=YKxL+tlxs?5?tpm`nEtx+$Qeo#rK|O!P0ji#n'
    '*4tVIQJXt@8(R_%aY!(kCn5hh!BB#QZK!6coXkWbZuz^q{@xKrmlX{eLA19cIL6s|oMHtB<+m<`J(s!3Fj+KBnzL8UGD1G913nyr'
    'sN6ClWMQ_C2XSL3b~${y2@MmbU^XgP*5YBHjTe9PyZ7;}m+RJ;NO&K2#3$xbt>@Qx2V&7MMtrD`RCz-;ZUVqc(Ez}DtG`PWu+dbI'
    '0a2&z4NHUtX;i_I{TPcdaOqy$ZKT@@2e5l&ixSnBAEMmtX-BOt`mr4(u$kHb8n4wFXQ9DuW$rki+ar>|&nIl*Pbh+F1w>v+#11BN'
    '!HT<v>OyWeR+=|CW?N~IVXTlG)zqd}5$zR(Y3KT00C`wGIb_%(suM@ZdijTMOhwN`FZ|IJw(lf!2khT>VrV)Ok0IEhG0l`2T4iwJ'
    'Xv()W(NwTh__{?r@INdI=%d<C+`SV45s-^XezW%y3w}i_Jg+j6=>;CL?^kZBc#eoEfYOKh{jP?x%{H;&VgwAW*rpFJ2Ei22T|77D'
    '%edVSG0vz#fqlrmTb!1Vp~KI-yP;GqW0bEovlQxQ@6MIXlUburPi85ci~Zfgb(%;{g02qGwT=_GwJM~TnZ2ja<wPJY8r58J5jA$<'
    'DxQ#-5aKR1r;42!OvF{z3%7FC3O}~*RGY5qMaC~HJtL-TxRp`x`p|3>y{o>h--o7pgqiAS0IWvMS6M@C(R2oAXaUU>3z}~I>*R$n'
    '-4(yyB|yJS%7<{Js|ZlbBFADE_{!TL2m+Xo8)0gT7ja$ux|0=NoY~v%fct(=<5ew^=5PtM=8N!cMaW4v&{bJL1Hp|$!*u>GT76Pi'
    'DYS)9w7|Kn^{wu5;&K=->c(zP>~Fg9S$;H}9xqk?krKONR5-`0Qpn#m-UIb~yK*a`SL{k+6gld)Wd~+a++-z^U1QTIRUd#nfKX5s'
    '6RXcAnZ3yT;fzczcsG|R8O2N-Rr2zR=JJK!ufyMKgf4YFT6(DeTgGkl0ndUwNCw;Qz2Ikd&di%XnW`3qUob%;;PiOec+A}|C~XBn'
    '4fgZSUTk~!N``eAE6bkyzBZM3%zz6&#m6+=YCKK{+^ceMWlz~3x`YKNln<vtpC-PIO^)2FSlAYQWwnvPm;N64z<(g2Jn%>Y7;(fm'
    'bQEH6HTTL^xvUw+>Ec)c+Rv%}y1c)$R8Idw04q~B%JrF@rA2?K4CcoN+LWIBF6jwxw@UZ312H~DiH78BLvt^{D*t}?M<oQO$)u(%'
    'jlXVymNShNy^^-kg>^_^KOR&U@M(0I|E>SHdfFjRCQvB=K2NDg<?^l78J0^%kAp?0l=-Ncc4?hua$scPyTECT;KImQD4Bm$jC2;_'
    'iuaLiO=<4dru$kj7`6=<tLLCmG!Ex+-Fo*2b-si<o;Y(yxIs~mk$SmLMGyBl15BMY<5KvLOP^U3wCD9mkvah!>qS@ycVWf8-#}*@'
    'l}D!Vv4q(8zTt-w{H$*$y;s}&knt$`Ww0s!vqA0%32X2Z@H0^m&pm68Hv(8%T8X*BONrtvq#wfNufB$n9xzvS$PzXGR1ojYRc0zt'
    ');RsJF!!2wRQla#hEp^WR$wwmsZ8F9ScLOyB}3}W-<w#JJe<_@2z{JKr;Q(c#G~VJj4-tIx#UZD56+ZTVW%P6rqU^w8ToqRQ!4$j'
    'lDqH{#W~Pij>^6<U=Z9Jf<12s*a<gb<Fs)u*-#5z1rohd?l_OWp8~QY9M*foJD12ku9A2+oE~Y^y~r)Cm*@LFHC)1^(M4elC6KM8'
    'Zq|<#tbl9Zd<*~lHjBM%?y*PZcu&M*>K7NNkn|7*dWAaaBWdv6Kf(U8Oc`<Vyxz#Cl+(%8p02sYBn}z*uW!o}8~Wl=xRBM=X5HQm'
    '=%Di|CJH#lgw>D5=FQ*0@Ob_C7YU_)W>By6%fKbtG$J!3ID@P?vMoFosW1XLsgaCGyv$+a?BIJFV98xQyCkzzR7tA1wA=SKr2wD^'
    '8%#5GZ&bvxFoDG7XHF-?2$Zc|8#b{Lxv4wBm+koQZpKe=hjPLQoUaCs#9y=9r5u$%Ldlc9sRPoPG_G^kYEg5vRS6Kd3SM)90Y^c0'
    'jyz1AhtuMQKC}umWBeb^v4}iAjbk2nvO1G3N;rpDc+q)~k?%f-O}7+9G5ckw`MU5&Yw3I47<@Fhr);qH2eQ{|Qk}c$!b)E6`bkTW'
    '&=An7`KC&~zgDPU53!g!k4pG=ho0<txm)i>F3QyU%XvSle@*Q=qhb^t-ur>Wn&9ig0f71n{_9tWnbAB;kR7TG?2)I;lp`#cAhwn;'
    '9`8Si)e3)}PpGo^)jKnJ{ZA%eWgP}qS-jVu5U5bBhN&cu)LO@J&AU((2<oJH?l3&QlUk+JGL5ZWBx`I6H9aa#HNhD0YHn&{&5fTX'
    'dO!3%3UnxkM{$M~Z;Voskio4EkjriU=*O@33e;PHC3JI<vWEz*euX6Qfq(&IEi$2$q^*|@0TEd2<Lmw_=$a=m^59&E+i-YON@q)u'
    'hV&Sqs}9}OJH$-4|DUWAdq!=aW@%S=p`TbB2b31p2XX&s{K&RUO*l#=dVSDsdm|9s%jZW8paUcHZxjsFPhLgk?FCxvFl;>5()gJK'
    'tq1m1gSnNS4lIEOY$n!>kP-h)E1ZP8e)iFm1?gseFQ|j)kHS-xrX)wk&R$xDZ_a~<D9?$|;vH9@w8OOEHT&s3M9q!BVKe3*!za&S'
    'V<pNLT5ddCdE!BUE|(b^>;s(rq%<Ll0YL|w=T7CC6O9cpJ8g`1JnAJgk{P@Y+@q$_3(eK<BOQ2WIxd&iUThd~B)y~PBrmCO0ckD?'
    '+>lQ9&zN44H-EjuD|$bF!6EIusz!gz=MNYGHh5*PP05{dIkS6ee?FLCccgMXgOvv)!Di8G_kQdJ9y;^dc(1{#u!%LySRyf=hpMav'
    'Y@fP~5QTLh^Kve7KMMK27K2c$y#fKzy<L0uOg?C#khV^3_2G3_(7yNle~0>_U%SK#>o*?$b7g*`F3ut+2x_#GWDQs5K9+#aV>YQ^'
    '78=&UKlpG2c7b$7evP-OlVm%Q8B;1l_z(WO)*Nlz5n*q^I-c@{4^BTEo;a#pio$db82Dwl)NCf9!7eVl-AfhMHOk8q@X#i@YtRO^'
    'zRX(mf3XEE4COWKwhweG98NZR4Zd6dg*NFto$od+dfE!6R-AO=irI0c*Vy><34FV@J%6UC#^9jn%!q6x_}7RizyR}0aDh{&ZSz4V'
    'y~cc<!vmBmO3w`xH^vd%cDg-c%C=G~#(6=s3+gyd>K6KUY--Rj)W5T|hIM%&6?H?41Wn%+v#WBS9msxL^b~3*x>&=yC(scj;?c%O'
    '&7vbK?KGv&*r}@D+Oa5#z-n|th}-AVYNq~|9~ub}WkcD>N25+OEDtv&C;WKY3ox^->GH2v8JSS~_TNQZ^&i1MW&A*-(g$>%tm9r}'
    'r9+&jRea+a^#oFSaN-yw*wCSAF6lmwW6N`vsR(G$=O8&Q1my3HP>p}zO3s&cJS2BR9iRC;S}R}*d3jEt+f*W{mHm{S=T>r{kev_V'
    '(}lDh;_BIA^gcrYiwgEe>LG|<pS`0>lDDxeqtHzj#p8VtJ^Of5F`O)*aAHVXuopRr)~g24(NY<BnH9>2My$E4RI=#Th2sNCD3(Rd'
    '_O)GrgIs7ZN1F&U1QXO+tuA2uk#R?sHDYF>#xphc9`c8ON!!P#2pq@<f~|*3hP!Eo{QmA)iiRa3=6?b!vY_75SRNETXK?KCE*)F1'
    'c6JP}V;uWx49v-^DFKmZQmJUW{@lk%;0I%YsY{o<IQM?Inri-91fv-yON^GxvlqsjrDlM;;70&Ig#zJ3D)(+*;Y9OX@F_x}HmaT^'
    'J<N>a8axfM+UUcB?kiV3W)FA6k5TAI_L9OG=x2j-QH!?Sm~zBpBiLindg<L`=H+9JI)7G60B1D>7O~6Xb1sNt-LRlb6lSgA>9g|d'
    'pzsqQ+*rUNj745tRE7iVqa$CFw<`+ev<IJ@9fcvV!T&T4#(xc+L?kvh7tvhFUp0Z+YUGuvvo{-8t39HI3=lH9&<zXYm$k2*-B=)j'
    'fXhPZRH|7?hni-WpQVoT;x=-)0DAosK__b|v14cS(#f5KnttN@u0Bc)^eX)inpR_m{41vxhRynS6ST{~&%o{C=vt)7+kwI}G<94W'
    'v}a|>Zn<a!Pl5*E0%%=sJfAAFhL0mt6`Ia;vIwW8f=!$*hFI2*uXGSE2X682d&C(7w|Q6=!3~g$#nIqb*E9Jj`vy00ra1anTU*V~'
    't<S1SvM5IxXZl(HAYAC)MC3qvgrDLmjV8b0nrZr2f7TH?dhHB7b{|4%MM_j=q$r>mf;JO|NhCexdL#Uocdt2W6#6>U{O%Ie>+OA_'
    'eiFnBWZp!R)`k3$W5))-4<Aj11snVqC#bkJt@q8hH7>o1Sq#sugtB7Tnn{w#mj(fuN1nrTVb7u(Ehf*-?7^?9&kZHwsU}v9DybWH'
    '&{T7UVv)S3Rb~6HS|qZ415q1+NPW{UhGEN3&%h|5mh=?$1hgj3wa&p6y95`<rt=8nMlz>?t3^?dL|D_J+jiT+uAc0>RvMI8;Tb{<'
    '{HmmXB3&jaI99xA|H*UU=fJbjjJAw><T0%0m_;eI3V<uGDl}6iFvYf{sh)>2vZp<IZ6cIS{Yn?W+SI^owcK>At-#t#MQqhE%=BMO'
    'qSRE%f6o*~9x+7_^8hzqu<_Tj!64dsN6}|ymqX9>N;N&-#!j*EYly`Gk7GiD=zuhD$vcZC&3v&PYhqumRSy5l>M9yZcbu@kg@^`s'
    '(l1fR-q8@Y7^Gp2DEMamcAC=swqqiDWDvZ%_oSO;o3>n<3i1@xr{HVG3COe>>bg6$e$Y*x3cqi%m&(4XXeJ{z@_ob-YiPmd=-FF2'
    '!#sK%gs?dEkGONmV52kmWeHh24X~r1;zGl3rK&&@d~Ew-)xWFzdq9(5$!f`B_D&%sNo^f4Vqp$&XD0v!-NMC_oR-+;41i)#dR=zL'
    'DK=(7BGiDZT_<ud>7sh$th%LylUq%;@en+toutC~LF!`j9Pl9!FWp)&)O-)oFHBUdgn4pOz#gc+H0&U?N<F0RS}Iy!;uRniO#^IJ'
    '>GXhrOYm89xpEb0aoALBrREBxqjIw!C*nj&mJ7beKeqtaCT&x+uv*{Z?U0G{keI_^AB#xJSkO@7ZxOywm(K80z0!ApX^SehWJ3J~'
    '3E0J=0$|w>*g<K^bX+TTo2=)j9~ufdM<E{MUGy}cJ;!Ji3=}p&dOE=>aPgLfm`+XWR)x|jd6f`z+`g~<C1^21mfZhnM^hkcD|Tye'
    'GoWjrFg-!EQiRBhKeT4}rZ4gRvOQx+ArkKgy9uOWFTr5^G7+3Bv|%*4wj7Bgt+?p8>-2Dv@33wVpm>0%VA=E#P_*95Us=Z6tM;_r'
    '9|BsH_NE@97|R64%N`!I`@0{AcQERIzz^VxlC@!A6+bbUt%j;-tf<Em7<o$wklv~Go|{2hRMWmI?Q2dTorAaJE+;01a}C%?%zg!!'
    'fvODxmkPJ#y2G0d>o<u^nK%upVJW+~uDTcFItVR+|9&hyvfXAB4W^qNdC<<)mRjvL5UwAW#b%P~hxu0h&YBb8%lagTapX)dxE|k@'
    'r;#Ex$+Er^0F6oB(csd5VKryCVI5R^<1>>EUqvi<9ck8fB%(2Tnwf~ec!S-X3ALDVn<X5Sm53d@q;fh9CHuWyJ$(3QT1c5^yDt<w'
    '!5!=fWB(5bYYiL)O4w`oC<J@EEFT)bV$9^<{NEX}N}$0sE`7P40?Jh107eW2{RuX6<ZZN0wA6HAwrw9A^F%jXlH}ODSc?^m4+Hss'
    'N!&C?df?}Pw)`?`rIiqFyNw>v|0ho9%9ozwyXX<rua>Xvn({eEpy1j68J<zXEjyuOI~Pl@WIDa#dNNpt5u3%5uzuPs>kj_Zn>(8('
    'qrwd0v$*(zgY|lK=5~{{8YEERAXp$&;PI1ayJPGD!G2*GP3}4m16-`HH(d4=!agF<9M#mj0GgVpxX#vxKq&Eg)CQ|`8C%qlNA}B$'
    '&V@`lfs$<++3QF+!zq|z&&EJ9O~@Fg7_`Q;K1o_=RTSgYu7Jyy3Vj$IXWW8}9oPlxztuuYmKf1?(nVn^14=6D>KiM4RrM<McwSlI'
    '?Dcelw%d)&s435wW?#5Q#cZAnhKcLrj|v+Fpi%}7pKt+5vl;dQx{|ng=7#pnr9jDev+OXdL;%%@hUBYGXKy;PkKv@}9EF<xvs0YI'
    'nUPKwleiO(*W7*RxfSaNwh=nD)1Ht@qCTK;5&=Mo>e29*7ZfG`bZ{MQ{<^xJ0RakA`#Hl6I7zB&?_koFY?kj(FP$8^@V)E#kX$0U'
    'Y=$(Btd0x-_LtZ5T+rVLPezsyAC7+0r1jwqujL7rHM?A}k?*KR)=m-Q@Y#@H;nzhN&kj6%TmLEXGZ@Jvl?gc}a{`>@^s=!nXU2M^'
    'J0XA)b~7&K63NuJNa35mxmX*Xztyr~l1ToqYqnTd&We@a=Io8Fj^!$FM7=0sxy!DKVz>hB|EY*Pbk|@Clii%GaaUIFI%Ll5VOSjY'
    'WSay3)QQE%_6Zxku3<q4rvVR@^hEm2#~Dgn(Vp{k2>?~&{jE_&0G4YZXQI!-FT|i%?)XgA!d8Vt{5bXj;%bIUR!~=>t86|)<6w)<'
    'x7xc@i7X+Td&tW^!PZ$lPHGW0(MLz$=t~-$v7$Rb&(Re>RG3rTNJsBgKkL-(e{^)SBA6JZZr4gqYVyrjsVO6cauXl!1pNLW@~d09'
    'UMUPBLLkU;>p)yuBpRE7A60hG*5Tsr8l?Ftmhe4DoRY5Jvo_bwg-ShQPKdD<^D};oR@;}H6jb%Gh0o|;`aEiJ)A#mR3RX>-x>^Am'
    'sVvgQS3nm0sY^g_Qa<ST)7smPs8OyNV!6>B+7;efS~M>r^H|#VW+(&~nAG}-UDWMz&T-fABA8qXp}iaC*O@-qby4sBEqRa5D`f*8'
    'tEL#@O{EEcNZm~|of6;hq_gJrFOOt!L3nUn6zcT0R2Hk3VZyBq>4&)(o%cc|!eZJgTKNPVw%Uh%>aF#$UeJ4c=v<@GX)CDco((Q^'
    'Rq;&%)TEd^Tr6j1=kl+!IaqF^Q{VKCJOtLd7}>Y=W{|P{7ey!VwAZ%(@er?G?H5x@IE)N|u(PPzcNI8(oB42%q8s=z9*{t*G&)X1'
    'EhiV}_NN7}g;M+F(GmkMBWJX5fD`m3mX{L%nveG@AYzk}C#f!l*v4X5H!86*m-pLIi#l>Aw`9&;g)>b@v9Qe_zwZWt@z4K+iHX$$'
    'p9MDl2xHQ&ywOy?)|Zk1G~H9yuc6Pa#g@m)KYg|_HhXxC8*4=X;P_8&?Hafgdu{VUlC>t8GVkpNDPWUFf29J{@#fjc$kGfqCQ;Z>'
    '{tu*7%0~DT7+|4DfOp7HCvOo|?o}bp87fql;~V38X8PgQvx8711<@rPeg*Kw#fD+|azWVp&GDKCK9+fniDG51&eBmmn^eCQ6j$%G'
    '7u$o<aKcw#hj7UFA&JqM1bppID?brhsgsL=d@6|Lu+yg~UNTl&4Y<K}(x;^&r!;!tvaxuXw&Pez&5wmGH#gddG|cmH$+&SVzpm9R'
    '1)jy={4Z#D#_Elc36{iSOh6Fg=N>>$z*bB%35{WlchNuRTil5ImrxD`z9Uyt&lhyepD|#7el^3#Pq)PIgUZ>wvK)w(5jxYiknzu6'
    'V$dSgLV_pI$^yXkQwGcm5SVfv)ITi|VJbFktJ1fsmx}^GDbK37e%~)1Op*PPV2@I(t*KNeTg%_q*a0SYu^GO7_W%gqzDEJRg4ai|'
    '*wKv$=XliS<o@E1ZITY<op4&iiKFh33QkHcG}+s>=8vd<^w|eJ^*yh-D=>#{bTcjn!9ad7bM4+cZ_O)J@G08On)!Y|WyEF%h9&RN'
    'am-@UQ-a}CLVoyau1f0$ac^|0{*tvc#X#KP{mk%Jn3Kydn_k~R;r$3Z_Jhk#%N!-Gum@RYvB)%V;gsWZq37hJ=H9+)n2s!L@@4E#'
    'RpU3qh#1l{NeSnfNPGc(<>nrZ=TZaf+EE6SG?4tD65HMNWoGboM$i2^f}^qG;|9uu6o<D-wsj`m7S%ye4xK6h&58%Q_D28mW(aJ?'
    'Sdi5{B&x(8*O{NyL;0SY#%a5VU3ywgAEwmF|5Yf&ie@R@3<)TdG5C#mg!U=Fg|go#UWsq{2JciJyl}2<hTgYV4aAtv(#~w=%whM@'
    '7Xc{#^IMH=Pdr<folt73CSzcpu5>+5-|yv`mybycx4z?JdLWHOFCYwLbs18q!kwt#gO7j2(+SLQX6#J)sevbG`JBIGELkUxjv&DD'
    'kzrA4p~}kaMtO5#;!|NpRSW8~TufCV>3bX2U8kQjMfNeFr$$%>BpuT)A*d7Bo^F`uTcaYr(86n15!C~lPlVANU}^V|F!FoFo<NTg'
    'DC!}&+#*x}&aTq70FHp|Y8cX==UF6=FEqPN7!97Mk2nt&KXub=+EQS}f!Sl8yBHM#5NY<w+7B!?(c1GPiXU#@ro)1&wZRzb#4Xj#'
    '^^*%s_v^v3c~=Ab8<*xkZLP6JJpk!m%IUL%oD~bNG#qyF7eq0_-j8LsqUa+>M<?Y)J`SW}<mow}`xbt{OAO#$R~-MIf94hP?a0%n'
    '`Wq<5MKMqfKO%(HX-UW8l#V%%MshQ*J0l|(YnFI+WnoY4$p8hiMT35NKOCC;0+C)s*z~6iDZz_Zo{lAVVAvyEChs1k2Rtdg1H+cB'
    '5RwmaP5rM>J1Eko@6Dw9B?^+evg(l|oI#LO3Lb~QjKj^fs$EDcx9I`!us_hQ5zp2dZF#&M^J?v!@qePSpbQ0>U`|dAdf5m@=dYfP'
    '`t$nRNVzi*39-drj;%&3y@eD~S52It8^L&-iC>4mpzPaU_t4-NZkE+Q!8upVD8{w|{r}23fhB7T-DnfYT`#MqkoxoaoCkyp&Zt`j'
    '=h7I!P{)BX3Ey)%a<#74R9k?fYKyG(bm(OJpR+k1!!nQB;%n7S*C&|~j%&GFz18#Cl{j45QyC1AKI)XzF244^mG1kIsWu~%@IAo='
    'u({E91<6+zH<C(ep)mpO_kAWcox&SICdJBjOmGMK1>;SMNgWJP9sWMWeb!A+Tyxwp`6Vd!R&G5Wl8-gS1kOa-Zr5cUy50z{9RTSy'
    'GH<THpl)u5#v**NVSq$}=!PYGa1fARQ*1*Egs5t=2^J_LE^ObEUfV|(dgCI38NSS<Iv*}YS-~58o&a(p-ORk9mA{HE7Bhd1#Sw@5'
    '3psllL8!j@p1ZRSXEfQa3!?bLs)xx5I~3H=zdB5$2^0(E$M{9WhW4$mhU*-k1*pvjdzuvto)$IM^kWv8z+-qIr{|p8R3$>Rs>v&d'
    'Kjqemek8iEXb1!wN*+s_5Xm36As#4qGz=R{NFFHn_v7Lczgmm>WQtx+X6&LR6bc72Bl9`G8fohQD?qM;n(leGJyU8IB%mk#Y2)RR'
    '_CYanJJg1ow?jWCSU;Ko-W}mGIqEvQAkP{%UAVXCQgEkXCgysC5ip+Iw{0*)*cwU|fJNQ2Y*>Li=PRM5n2+LSPa!W*UUO12_5fU~'
    'iRcMa$*PFOOy&l9BoBOES89Yrwq!`QyKNKv;dlK$`5=s$Jut$QK;_T~SpeVU3bccBN0~OJSZR?SC8Zt$nt(!sHx8?KB0r6wK~HgL'
    'cSTBqgrDPW011TQjn-LBb%V)sUh|Hf-&4rVRLoNI*ws#MkPDbuj=cinGK<|Z4PN2m2kAku;J$_8+w?0<E5JeC)_-LFIm<2#8STm#'
    'mTKl+4FKQbliIF9>IrhHw2Bv<@7gHXaqjE&oRUjwx4Iwr<tv>sU6R~hYFw+^uIHh73@h76XPrk-FQsUXT?&IW)!WsbL|(3D(r=vm'
    'Oz+P<&LAbTtbmjIr2~M2Y!F0=2JMXuawu7%i-&zl1MdeQLn_=~>MI+VT7ClliYF8fM570j`}SI`BR=V0dHP7aR78GE?Q<_Xsf2f+'
    '3JxuLvT-=BF<ORnq-8Jl-tt4eaj|vw?+9aoz0D!-o_`Kga?gq_yp0U|S4Z5t1QA+R`I=S<x-awfG39JuJB`(tu1#rM_%0gKN!bLu'
    'fzi^JpGXzqZqph#U9YK~uv=*elv)5QGiwP{Vo!~N0CG4D&>TX0kQA&(nQ#J8Tb)>dXq9qx>mGdfjN><Ye%=Gf)7m2Xkx`Zbb2v8c'
    'qyuf6=CYgy?f}FQ`RV|@dhf3rrnhC6+w>MAiDm>HJV_hz%X)H2e%Bx^d;6+MnaLLpk4MH;J`aDs7BDS8Y26C8QU}mloXEi3_&SQ_'
    '8KXHYRv>k^_j=LG%jOq2BGx!+->z99k=M^PdVq=*iFLyxoi1ozC0vOHKZH^tdW7K`kDZ!jAw+tl)y&ShdWzcy-U@oO+v%HX+@tMO'
    'Ta!D3p<Srnzf4s+D(&@S4&SFgEyRmLv-}G!v*SXV^&&8E+i_QEq?HReJ302i=aItCFgin}HT_^dMQHco7o{tj@U0H=7Pt<q+-+Wn'
    '#lv6i*?zz3w%*~nfPvJ=R1jHV7_4*`+()o+gAq1r9*OE>mWVFzCO$4tD_iJy_7HCgV$6tQDRfce7(&bUdwjw~*uCT&5k655E|qzE'
    'p1IQ(cYWyvl$tKeIvID4DtyBA-W|e3ZFvG*SSX;Q7VR`AvzjRSvZR#;UE_M6h|!sv41U&e8g#udbU|YfC-c^<6a$l&y3{y;i6#*m'
    'VkR%~XM=DE<Die?c(~m??1&X<_1HO0NYQ`Ozz7cBT3AlsUH8M-<KogvmT7O6fhtCXUOFH+-FfST8j~m#<c;&r(wY`3Fa8FZR9GD;'
    'se}H+vo8LAvSowZUxUt880G4I-b0KqSEvz4x2s!5tI`<)k>@jn41cBLS)?Za294;Is6k&-4vI!oIG0sCwp3h4_5<3+YHFpyOobhQ'
    '7^<loHmj1HZ=gqyA>ry9Jv?&c6qX{DW4$x8$Ov#_jfGz>Ea+WzNcV&7%E3A>C4roRFokdfHJXMKZYz4ppH@%yWLSLjG?QhU8pZ7e'
    'P5WlM{KR6Ixaz+(nJT4V#oaM=nHNYfx~q80Un%xg4^avx7Z?V!wv@HLw+b)UD8;H4OgBWX25oLsFT1%r@Q^}=$rhH%{0F#H59u3*'
    '@J(9}4#A3SSO1DY{>pPPhvei0-_DlLo8y7t(ytbQa+@iAB8dpos2|0lLQ>QLIt5V!X>7Gp%<Q;Q5DLs?@Cm`4$e@X51t8OMSz!<k'
    '^LFNxdf<G)gd!tcxAmQEDay^Rb^`he#gT30cT~qKDsqd_lu8_X82@LXD{jP}4>Q=51k=J#;2EjEfhx{yW`>q9ng)N_;HcD-VIr$&'
    '><qPe%siXGC${?3McC2IHs88hxya(Zl#*UHhKRW+!E>T|D!um{cN~e7F^>Ke@`C8N5h!{1n{r3vc(at&(QvL=2ts(Zi3F9jM9$eR'
    's*|@e<O0z-b=uM58gv^4=0!V(pl&V!%mDgaL-y?E@5T~Dm?K9|Rz+$ZznknBQHwvDasnW^44T4(%P%1noJR`~qlgeg&jD#pV>_-j'
    'ssY%?cj6ljIv-T91nsn`6PMI+zr$2*<%XtYv(Y|xg1O3%d|~l1;ZFzf@`&N#w!N(xN7wX8!-_SV<=k|Gjt$_*HnW@SuZUmU1SyZX'
    '1tqMwzVgvRmfRkXSZWU*2sCg^?{H%bQ<atvF}HR<GXyL1ini}-P(AAcHXjMO6+ubjwLx>oewA``O>0qUU_O7Qv;5xvmxpP{+MeDd'
    'y?c21Y_vs|HrkQ;@NT<5E}{IvBDc0xc>aSZ;_N+L_2aYy@?d{0k;*Q4==?4NJ0)Op#zuwalOhMmuuZqlj7ZO=ydAz+r$*Hn+o5*o'
    'GK;-mum}i^Q&}tEB+f{r#SkCUEYwU{J-lBd1g)6SO3bgKGMrXYppL%`P&gb`s?SqKjXdnfBUx=r-Ea#z4iA-15h*R$lSJW%IK?1&'
    'cb9d;(|MqHa&<qvP416kDT^8FI;MOf**m`KnEd*|d*!9GgB*k$8G37lmm&_YkIq2h&3u=9a2jXHC}!&gy`rAkWaGQSUiwh9ty-PV'
    '19QCF8c58Loa_L2_DhhLlUv*5Zjg`fqeMbZqK*ZZ4$72NsL<poBUf2By`w9{lFw;VmUi2I%vjMnm^&n+N6b<UgHL>P)bOtmVj)0n'
    'n%RLlM%|lC#rCSXS>R}}8@sMXh##>oCSNxZXf;@M{z>*3(r?>_jrrtQ5!2P?0m?o!JscoWC!ee;q*17-JFVuo#8Q+Q0MX?M_9|R{'
    'B6eE(%kT?02!q_Nv$PFw^wa#8FyrzySg#l~Wj62!hP<;V0SM>Jt$dY|PHwtN!AH^EW3p3U1oqL+=CK<Hu(HCS8_Hf=P&}Y)%yIWt'
    'QH?2*+~HEgB=G^DJ0t)<5Ze5~=mB=CsbDx3bQ&<uerZ+>@eU{A5@N{Dp0Rhq>P8VgRn$Bb643AWqEmdTpSo2n;baaWMeHZ?8K_#7'
    '`gYJ(zkZsqHBcb14mB61#RJSuBimBj?1;ioyb+*L;=9K5@9Jy-Wb5yOrkjIrhV92wPoLK-3h9<p8FNKp4nFDb>yE1Uey;Ny;YCf)'
    '9e{HAQHvW^A?(Z)Q=!q!>tPmurnX>{9a4&aHA<e^u-wFa@%UGrLWGQw>9>0b6+M!#{rz<ef0Ma3l8pyZqbiq&@ei#lCP)Lz7epr9'
    '>$#l^C0bD~Or~O$2QAN#C_U~8p8Su8dk6dyahvGr9fQ<LZN;bJ8ep1eLMUT8Eb)Ev*G_9Tjdg5c!T6VIp7#%CQJ4rnKL-4PJdk$7'
    'sU;a{oCo%l7Z(JDI{EI9>|>|t%UWhey_iSxKeVNCf@il^G9SVE-q#C#JMPaxAgI*GF~gJizR#++@x9VEAgVlGN&&1tH=+F_cMWsN'
    '^($Yo@><aP#!aU&HQ*%$)9kE++6VipVq&&(?ika&zG2dmi*sp*6Y?W30IeJSZiFJ?0xx*eKL7CA-YK5)qPo%1tie^6R8n|la*_Dd'
    'XxD*EbTs{89|AiJk_o?kE?ix(mOXNby>biW1hop(pm=TSmfF~c97p3>5d9Hf_kg4O8w54v4iK$JV?ia|NtP!?*!#{281oF;ma0nm'
    'Hv@7|izb)U-<&^LKXELD$<&Ds;E?UA2tl85=Px7J>ci0*n4^g##WW0xtC852o)znR0Y5PvizFDzsH8`qKhFRZM<`cczOv?I6SP78'
    '^X~SNSBT%-PVHNd5pNfJ;)$=s_hupUmpi%Y)I>uDZ1}r~XJfh3{khy+&<i#TqysBy2nfytqM1{ZV{NMSi0H~AHF<}W5dSPmswxD@'
    '@3x?ZSSg(>GHvp{n1)a}LMHc31;p>YeppKclT~E*w%p$c1Iv0Tm5LXo43d(>!-Tc(<SxZ6r0aRvK;0(kH03Wb6$smWOv!LWLRU4o'
    ')8RK!gi-(vQ~%hh8*~-Bwi&#EPE+m&ywbmXEtQIJvhHvO`gq_+!a*FKu;iToehusOM3aW%?f=8k)@E;aKjhp3@*1n8qb0Y;v0_qW'
    'iYqRjS%SNb-H({n7XyP8e%$9hg7sI=)c4j$Q<Juk=|%=~epQqPP(hE>p2V<ba4DwyuKSXU_kKy(K)%JwGNv*ESs<eqGKZ10d=g+p'
    '($#ZjmzTh%WEd-l2!1l=G%3Sr1IvAjt-PbljgPCX6R&6rsp1&$jXHAF<nlZoK5IgJ?tWHsJsA!o(-%3SYB@i8%3d9dx+5*X1KQMw'
    'M>l>;mzn%?G2y6}0r0TBN|TN&_|Z^J2))njjIKRMi`0qPbhf2gkNpV+JnzFR@kuu`kL0gT&K03LVUntPiYMq{xzWq>>}ln$g$v;{'
    '54_K?MFuK6n6Swo`#5%H`Ch5#6eQA?ZSkt^J$dZ1$j30{ar9Tl5oFf`%PR$eBX~$Bvgx1FU>ORhbyyQ@29`QDxJ#%TJ2pGZLCXSl'
    ';k9$YB*Q5l%hsA+u@M)(MYyM?w@YJ<Fqlb_N&&*QnaT;IO~3h)B$--uY^b}5es$cXm|xVEKlcG{2m(mZ*=JsK(h11NHz9sT%vs*K'
    'hI?LQ_tv613|Oi2C|wte^Q!4b$RQF!fee~`Swa|pQx7-hN3Dd4FK_W<Ep2>`9ZkZfQ3*rEk!*30?+ddazf%s0g#zI-soAGD9w*VJ'
    'Dd&Z})l>e5X{Aisye7h{VG;=U-k8hbDf_a$f;rtGl=eo9Nm;g4BpQV8IE)2z$T>8_4r23Cd;D={EBRHSUod@RCS~{HF(QG$jjo*#'
    '6QNJdcG(3l#;_WJocRWelL-sS;%DWdw4hkBIJ75e77rX$r9Y4%%ixsZ*r|9k7l8a+bv(#T3KjMOgSvVDM_2Ki1CL;kmf2eqj16|R'
    'd@;10QRw{ypHuIObu6^g`NhomK-M%}em*G_412#Zd(|wQcsLxY^}yxUq2vU%*U3=&y<i3Y{&?9yPtGSLREW92rC?nCmcG`*S>Inl'
    '@=%2BRILf_iuf4i<o?V#g-lYv`@-H%<r9*`ZE^^mtwWx^{2fhulA?DM>m>q%;saL*$EvteH_yEbGvXm8PjePd9KNW2hmMp>QTAIO'
    'UAU|5F;V@q-;%nMux|gp_dE6JZ%3+V|MSk)i<;yZO|UbQ8HGs!`2mM3Q-;R4zJ|`gYB(Tim%0m)7z@oxJ8YZ1N^k;{N75{q602{V'
    '+gVCc?*`lqjNogo2^ru{SBwiLM$gS%MylOjoVK`tZhyq!ya*63YyB#e<>`aUq4a@fHy-+rpS(>SAFhJG(}GC}0_q^ykVsIkx-0Xc'
    '(n4G3dLtEIc`UZRU@5Xe@gdOxVV*E&vW5C$xXit4Df_FF5$~3BmU_Y+)X%(U#45ei(6v4`S2A@wJ;xc@gX&wrO;k6{kgq5B?oi}5'
    'wi=0WW>c!RWOeJdM^bvN{)#iv_v(Z+@B255qvvQ2J8mQuKAj)2Rh+u#r(1FaFz4*M>Gru%A#Xbv>&JXCgx7(w&F>E<IYDuQS{``O'
    'c9og;ly`^HO2Ol5q3F90pUxbO)GINPP#1A@r=Q6owlo4%T3Po&pfZ|3apcZAXLNF!aH;;rhV+X*_DOdOp+)`V)dT2xRm2^8ga92y'
    'u9RX?L*GR|0dp#;&D4=b4PkW2&-nvf)9P~?Pxp!;KHibqo)}~V?~f*nIwl8?2fPa^`337y=slG@_bO*Zg`ElGl?Zrt!7ZCV1iHZZ'
    'nOgYB>K?8q$K<Dc(Pf&Xhr#nHfb}u(>0)tCfA7b*_Y|f%pP(hYe5TGW7I2a(*l!zesK6Aa{1WjC>-}b4hQI6DtK2J+T_&?r8bP;f'
    '$}Ys~Z?E_YeZm_H01#6&y?U28ffsC&QhMi-ep^jA<H$r5PKj%J+fejPIkU>j`h>sn<9h27I{p@PZX{j(UVz~-piBFUh#^t+*n!6('
    '-nDOd)waO9o%w*HDb0d+yDp`BDC|sg3BFJnHzHFlC2M$h{0H%0e#;G&B$(u)VTfeU0#mFR^ud5zVogP{fNM-2!Al8d*)8J%5Xw*w'
    '!P5SI!(L&9Bv{ipdt=OhH3!Ibx;GQVSj-CMtE85i4*&)7`VMJ(X8d7e-Bqup8}zO1F{G$k2w_1}$8%uX0Jpbd-eMTXPoi4_+~|nU'
    'h@Aju#M><hYR!wOJbo%wFjB$OF7q|(n=t&onAhD(M+^`&YTmJ_V>m|WT#3I8gOYJaBS+b6g2-nYYBweo%*cb<S*ia4np4y=1T*8!'
    'x_b-k8MNd(=SMAaSWx@zi-j?)#-H%$O@6scHY}T^h7fH1;jt?Ibo*_yRWn;qoJG>MqnIwK(nCtlA=vhWUYy$twsN*q+g6f_vpX&?'
    'HlvH`(SYQBhfndFogriJFQ&H_&kcEy7Z2>8ly6U;JdwDW1Vv5SXH;X->|R%F8^E_GrKXtPlLK1;!Us($NN_@*evW5{wz9yUmE)*n'
    'D2rOIkQ8C(du%tJmO6ji-Cp;^8E-gUz#qZ;+Z`Z*ROnv2xL|L}BOjN#STB}odtd(6WOzk49%FYLn4Istjsbg}GWoOTVO#h(aaPm_'
    '&+p~t0XPIiUO-tssq*KPxe)>!em4fO*zl8U<P$JAU8I`)TjbJ#M>cb_>pbro6gH-woQxa{+uzo}`8QXye%m%DfsMQ?!=t6kl2Bn{'
    'CK<(}If5@r;%qdeS7hxbl5SlJvo(ZV{wnuUrT|33DnRMZ)BsGb%O125>zP)(ik>E~^iE2Svm~;kxWa-9RtCuo#L%wy|Gi|Y*<Rn3'
    '=9=Uy&(X`Xs&n0KoadN^%O@?movnJ5q{@dzI4U9kUH<UC&$%hw%^_^nph?jXt|1uR4+Ky}Q;lz#kpz0mXrvxJDuTJsfa$E~6xxLm'
    'u#IwtAG2Yz`U}~-cEZMP%c?8UD)$M_OpCULU1N+=<P92<VUV9a%56GK3VbK_T_zt|IJw6kQI*NUsZ$pWVW*8VaCZd~?~++&>37MQ'
    '`|$`Xe<2xCN#V0O@ZxWcV2h*Zlz#UPop}D?{*FjBZ@a#kr*MoYEcdDlNK<8*9D}-9CgFW-7Wx<a)WV^RS(eJ}ELTQNI5jKRoptor'
    '%+Fss8p3@_!z~hG&>O4rAU-BiR<Mq6uNKOJBxZc!o|3db^F<;lsF{(5V#t9``!Juv*2|nOaD~YmKfP(UFcw8vu$YaF!=(UYg%D+t'
    'Jf&^Lvid#y2y9l?kD?*tiv5>1m;RVH{q<?MsJRZbQh?hC)52|}r|0BwMPuQP7SZnz;)0?z09*fNij&HHQ9JjE;whMJiN=*Fih(n7'
    'S-Pzh3uh-@((t`I8CIKXBSjiq$$mU?3Vr^IC&sDTssF3SLgtjCIwX%u<32Wl2h{NZ@TtlWni7`sQ~^3H$qRSpU~(F)X7#=VGi%Xx'
    '*N6X)dhSu${6Rv0R@#Uq%mXV?Zt5d=PPyrO9eBOmeA3{JB7~9@&CyZ?E-HhadGu<k0@FD&lxEOmqyr?kME}9KLcpG6>0u!F-A)Ki'
    'Tz<JKVGR-8P+O*{`B}2H@iqi-hj?)ZD;Yw!N{|AuG6zn0mlUL9Vk3s|mo&u%onC8_&DYyXRS-211Y&nw(!0Qa0EvYK!y?rf$wsh7'
    'NfaZY=e^HE^T+FwLn|bZWjF9W%xyc{NJcx4(cQhiqVy+K*1v#k*^_6>e8I2rhPcna)H54@eEKEie-$fMVAUe!ao76VbfMZjP1UA;'
    'B$F%w`S)r>7@t4)WN{e<baD<b!5~8Tb6;6Tn}Cf;3a=MVCL(OfWLkb8KsSqaZAtgHvu$I&eTlHG)v_Lk_aTe9+${CpTR9;?$Q~)F'
    'wH9E0cjyB|@~dJ36$}<~+~Y}tAaKCXTEaI><|w?&iEtx~QUlAOSsDUx{aE71*N4Lii9Un7!G_=yt_<LJipj4lRDqDQyI9ubaKSbm'
    'j&<{ze^c@4&uRg`U#RP*QyxF(BlER-1<ImEvjN(lGVk507MT{U1CyUvQS9_S``a;AOy2SOJDAOx3)<2?E_r?QI`$#KWY^cb2bv&Z'
    'VBJuP*@ex021OAq5+cG0d8n=FDT(~OHB;@{kMT<utu+}YYSprXIm`qxv3)&u7})r`NhflV9KM`-VueID?}~z`r_*5EibM6*R|+&B'
    'mf!pMx$f-+dLp5XD~m<t72V>jVLmSdHKB!;P=<$==`GeB=-+{w_#aZUt?^F8*e0WgZxL?@*D8Ulic%`-E%2l}sbl|OQ;<jhkbfP+'
    'iL}P20j6<)<7jo4ZJD=La^5hj=I^PY<0Kji0bAxY#x3288Q-_XJhg+_SB(Z_x4)B8BP)+0#aK5XszPIEw-@a&4v%Tm%zI}Zj*CHn'
    '1Y3%&q~t#?`gP5)j3v>c>y_JI;`!?W-vR<HU<W7EN*AmUW(jzs*CIRfv<JL=pIREmrVWaDhs7qyDz22;Ht+dn=$~1TLbk`2^Hyi3'
    'cexuOPeOQ^!G~a@Py}Kfk7r_F_AXWxsf`|QYRI=2%_Ao`d2tN&hzY#Q_P)q*x-v=iTu7v=NySamgoI!kf}%6hk_%--t25WGcOSfc'
    'a7CdXX3^l}1B)w$4Jbn8)mQi4Tu(Ha2q!<UtBagcZ^csCMA449k{-(Y*(o&q@bINbS<sAaqMLaZa4SAZ-b%T*;g<KB(Un*2ZPW!b'
    '7~i6wcpN+ay~2wqVeUlb>!NC-|8aZ2nZDcVJguI;|CFpeQ$Jri1AJ3s`fS?TXY_Ir@7=L|K!PnichqOdDT7<2$L>`3>K6f2m@``Y'
    '3^_btQ42f3tocLhAsij3n?W52y?Lotvp8h*Fw<YFSBJvr!A&b|;32#xoIJNuUNntK2u+Xs`A)=Cb@&)r@@#7aDJkK>fo69KYWS(G'
    'x*bP&iC{dH7S!k9eCz+-LDt&u;GI{SbGym-o2O3?XL(l4T=E@w%8nb8Nlerx%QKP270EH5Yf2!yyp2*cc$o+>;Zy@~GcccRmFL_o'
    'NQ?mFf_j4Gtu8dbg~F%imk3|T7N7gAJ24>J!Q?m2Ri-wM74{F^t1u$d${!_(xvxeART6Lg^PGr$f}^yp?fd`9&aso-o{Yh(+c^;&'
    'S|YCEP$zcDO5$}8yk<Ifk9i;#9TKM6=G|d?6?mNbP`W){tx_K<dzb94QD8xoIIsVbH_DA!m4zCSbiAMCL6l{STHJ37OORnq&);5W'
    'tM?LGp>f+V2@8t7a%rQ5-7ymPA%uH{7FVE-Z(}Mx`f-k$*{wf?os668Y+#D%(sD+z;9`Yd<WrCz#WlhoUF{M@6?yc58&|gn7U`)Y'
    'CQU~fo}9xx3{XC3!y*yLGgQlu@A>AW8826y<&svJZ4yL(Vk4wmzYrIy>wYC0GoE6+C(i^t;&t!CkPClQV$Q`2$zo9_^9#C@CXA!J'
    'XY6Q-sc0Fx`u7b-^yE31W4=SxYSo*~F?a2cvE*5XSqvd0i(DRikl!`0(iao^*htTjfU4c@>uH6z#vCLd^248<{%@X!AocHqF8C7q'
    '>b`pSd|X~Xtl=pUy<l!4gwT*1%82q@67|vp6<b%tVsIsqBKvhzNv0w`2%8i|hknSQ8r~#KpyU?R!R3u?VKM<n#i9AL3C*;>hyq1G'
    'ze)F|Gy_*U!@i~x>BR+&vxse#FtWM=iGl79SC!=wjEGnsvlC;vKr|XMc4JjZ?X~Bf7e7N!*pcPLB+fVO1X}PB4&M;}q-x5a|DVsQ'
    'D2^}ab+Ziw7|RRezIn-T8J1G?yF}&w_i$9dtVJTOtlx{Tf}`#ye^6km5Ci28Ei9#J<<o26`-7RtMF{EVdVNC|Hco*-=r+!=F(yJj'
    '8A>VHDYhI;Wl%dkq{U}}tL!&0#JI#lLnk?{K}{)v&<w2Wf`Et+@aF%b?krjv@Il{c0d20m?lv==Q_1QSV}u!^^7F=z(~JZ=3!3_B'
    '1Vfgi{+tMCY;7OGU#H2`B;NZVcHu*tXe_N(p<}UE(0c!m=-|2tmF#RP5>JZTJXQUCdQ)>y;17Y91(EaWFWnx_dk}n7SBmET%F$nc'
    ')utz1Flt8%-XFPD*Mt)6A95*71e;u1fp=o9_|-1O*VC8@c2@N~5hPz)s>i-;4`bnmV+&4Us#M|Cb-IfI`ZY-BT8%0Vb3F)Nhx;|<'
    'ul+yu;|n3mwMFD^ZatTeFzttJ=_=Ad$#hSC8(|c%qgR9glQfs>_mYDR@ThW>Kc)_44q~F?o0AWn>YEt(Vpy_@g!Z6(1I890b~c%f'
    ';%b*)^6!{sG$U}EpsW^@Ze8Z68{5i<_yH{nW7?a}%hN9}+I5cbbDmGV)pAZo3{^|@w)dh%SXO&BE6Gn<ZaHeKx_f$sm%;)Q4#LT4'
    'Kjs=VqlX@zPgT4dJ=$S6kOHq|NQ(fzkS1G@*d)s1HtcO`W9^bHdn7jy;iMjixo|v8aAg8gbw3~ZzU{jEpKqhI44>aeAKxMXpr868'
    'RHm74#Mf2~bSq-JG)&|d`^Z6w<;b+U3-J6hs9L<`z_GSds4^Pt$;4vFz$1~e!E?Y;Ra}24<^~S6-q(%(;0Kp4I7WyU>5pBxQEH<6'
    '{9D6wJJK|Zm<5jDc_aaekQ-J}93?^0_c{6Ur&T`}BvqQG+yl|`wJfB0jlsR{gO<uhv07(*8op*!4@7jpo3W2}l@ae{xCK8x9VXu{'
    '3>N+O+gwywls;>8d-|lKVmoH^-htWM_D7j>jM?9kVbAT9SAV;+=pRxnca|3$0L)@rglPX(as|<wOv&;!|2>56+*)(__vNv;Ze2i_'
    'HdL3i=~3mWTqo;3&KM{JD^dynSl?>=)_iqyox%bF^O=B+vd>LI%sOqmuxuNJ4W?9=8*_lIu0xQ2+UUTPo@3CRKL9FmU>;~<{ykN^'
    'plEB_C*<kO+;T14>w%v$GD<Br%BEyPHN>{!GqHfVSE=c_3;g-b<}(KvC8N1swcuNac~Goe!jR)Am@LpHP!UVeaC4D%O#@E9eW$?S'
    '-0P<##70F(q}VWrHSwr(t}FkAe0uH$g3SGs;Pq#ao50+5LFHO`h%X^zLj5NLq<iB9>0|tR0!lzIMGbvI?m}HY#%<lNe7OGB)B=L|'
    'vryj}7kUGH-x^_kZkug_2UJPFm<8Iis6q{nu;tV}R}m8aV2fkODhK-~uvS4_{Y#i*Jwl2>kh%tqNF{kWcNM;KcSWI(f+5kIu+F3Q'
    '5~{ID6_c9QPu=A6f@X;Q+F!x&@YrTo7`P|LV4jXL_Ygx;Wni1}kj$wa=^>EI2FM|MOpj$e{1$*;y)$7zFK2ESWt0~4bJbchkuT<('
    '5rbF89D~_WdiY3MhC*-gR)0Q)M4ev-u*(OCQdb-`=(lB-0g^G@I1II_R$<;$)AYiDjm81&)6(;3X1?*SDVC75X8awR*&aL@LDpxs'
    '1Yf5@?=2#EgGyJjv6kFeTv$=cu3A~H>Lw5j%H5R1rZYqPEQiICm2S<psnL6Sx-Hd(sWJJ<7^FM7bE$Zr>Y=J81ol_NFn$$mSuw*R'
    'h4!8w<ke6v2YTTzf3U36X{*sfdVCxz{v9%uqu}8*POMTWwT%JZhY*DF=BRe{yfWvc*RAdnDQ~%A*aFBN38}Ez_@Jqm^1tPtJ*3S#'
    'uXik!MNer4TXSH<R0Yu_3sX_HlKdE7Q=A6od7}|E0PZf)@I(Y7x8=-u-h6n_t=mGN+x9d;%-MqeW?*$aOs<dGSuS9~@j9alnGw#!'
    'eI^|W&e}j=*n){=-K2jYp!{^i^$O+$Y>&kZi+IUmFr&e{G$-AdDRay^awitmjK%qjKZJILUMFzT=rQhi^+a++$>Jf;fHK?uLKU`i'
    'vm5A|uPYdW=tV+MY&>`~l+@R74V!B0uk-;qF?hP9qc>&-v%kYtC~sapRiKT7@_0N|y6{C-wv(NGH?qG69^;6lZq`17U8CQ~dhaLc'
    '=oK><qVDzkJSE^3RKc#jrqKMTw=*^C7*aauRYYf$Q#sAKnXGF*t(T~AR58q;q96ZrpXZ1tyDAUYtFv?ZXNbz~XGwC(HUbt1w)!ve'
    'b#_6~diY#h!ViN&2V>EW5{0j;hC;#oA81Dsvi(5Pme^AUpsn;}HcU7Y*l0OEO)s~D_?|MRN6^ofAz*WC38MhpIGgC0$a;TQBg|<)'
    ')@-ai_5v}r;!@zoz?5=y8hw>B)EDXR1&*=S#`3kZ-oX_{1dyBZznhca-!eaN%Cjx%Mw040Yf$Z1))=Ra!lHX!wt0B591?z&W_H>S'
    '7J+@fz_sCKarts><)}-uq()28d+4;KJNEhuvFpX~wp;aQ_&w5X!(3%rZOIirtJ<!%u<8h5stS%9?H&>-^qpMr2ST?OcR~v-rQ+!2'
    'mnosnGsUcm{9PuKKasWFX+KmxDv2RWpMI%)$0lGvtWR;EK{nX%Dp<2;m&d$4Rx`eg>}zEQSKM=Z04<~qs`Ndx49<ILC1vg?QS${8'
    'G&S9v8=eUau)v%m-G`EG&l>hqx9LyI!c*oWszqD8J(k-<^x2QB<4#)%KDF1>Zd}!8;iLEMSK8nd29Z?~xr`Nh7I0R>UiI_mRpXG)'
    '$2BebyUuF^z|znc0TG)0dzRkDK45&?7%9k~I3)i0q1SYt+J|EVXd^eN7{l_+-QYJ-Ye2M4wVQKqQg%zs?+dY^B*n?jCWczpR>C|>'
    'OY`{8=bJH{c1zY(uI2up%YuY;Sg;j%_@11+ZzWn6bq1$Aan#F#7)}G057tPoA5m;J`Gpk`{gAz(W_gr$mH9b#+kYkP8o6=WFj3|C'
    '5{7+yvy$cGQihjEZmitMZP#6CUjedg&}7v0+QFT14Ey&E<-q^!#1cw;xjyD2?XDIaj4^9cw_k33E_u$m$bZ7nx^hoCs+=;481(c4'
    '2958v)9iJRa})>H?gd*w;6t~%+9&~DxSB{M6T|1Wx7HwYIyCg>MIk=*7fSW4f*(|WZuw|<t-`6$lDMiBr8C@ya0ONvbQ`7Ps7#Cb'
    '@TKfT$?i#>|EVv35mKp{cB7y&>jC5FYEcZJ;M~?P<l)`F0Lyb^nH(`RU>`I<%Z9vbx-<#F$eOecQnaO*>Cd+Ks6h%8#g&n%swl$p'
    '1+8u73w8QyG6BBJoynOOd6@WVUWsG5Fg&fOwVgEK{)l3U3>6=8<jX*O`?WB6D3;4MDXMzhDgwcxk%Zq}t6&2-gNf8n9fgM)xQMD)'
    'yXH$7nf@ZK#ZbGs>ZrwYhc}zi1o!dR!htz=vGwGbTqtliCQZIhQgRBge%^P<$)(RSnt*DCOsfQ-E<|tjOuocW{Hm)`33)5nf%C#a'
    'h}-x)3ED@qW21@r{81d7YavKQm&DfAfYAPDo0`WC&&d0o$xd%$2qJ(%JrSoL(a}VLsL2Fl<Qi#g#xPynA`5sb?<tvGl0l0Ke(_)`'
    '5$)MO^F&+TSWgJ2o|!@!8iwW7Q~bJr=5iujx!s_mgBFdY{dN&WSXM{Bc=>O{SxU2u;-m*j)QS5*`^Er8EogPhx`GAeb6z`uqeP50'
    'XP+~@{|&R19P`&THQ!Z7?)4Mi&cYEE#Wi0Fp*S&e<CyB=4RBz;tzH4n>uom6NY)GEmgY0IqChjm3L#pK94;qD4=pPkL!l9ZhPH1f'
    'yt--@C;qro<p`HzLFmm$?GwTz!!-NqK1`$m*)NkOs2Gr=@EF5wLf{E345*+CmNJlort?W9T7>SE)q4}#6fX=N2RD4Z$XBSb>hZTw'
    '7<LCZs4cv$C<d0|aIEyj=4QP65Dtyego(uecq0tm|KO=aU-^;TaA>9*HT7#Hx5kkKI-JUb4fz=HJm#g~&;mk0z<D|iDRuuEOeN)r'
    'u<l*O-~3b!Fr0L@9cC~sn<R6$4y^hdy9NdU>UuTH!z(GB`qgrMLhtgnnj8KIA+t|GA?)|kzG7lL_tj9T{^Yww8N%`_`kyHueZcfF'
    'aTUq@7l!EuSG~=>ffZRd%t=dFQk2`$@~pHOU{v=Y(Y{hYGIGP}<TiquWDWP*M235Yn2<dGc@jo|Twp>&r-3!NMK&Lo4XpkkQ+-9U'
    'd0Wxyqdpu|78GS4c-K>iOM$7VU-C*-h&hKGXS~DJZOb4YsYn#<+so<EhXM~2Wo~3>zJdN}DKs9k)4hq)u{~Cm_cUJ0WW%b>K^Vi|'
    'Lzbl1AkNku0cSS(uS<cP+U)x7$x#O*<JrX3+ywOtu$#VTD8{WYd=KMDj6lq!3(^r4NP(lWJ8e1sl*Bne=6+-P@77OKp26-wQa%=_'
    'Pj%h_@vOPtU6#D;mqJtN@+_}<RQi$dA=AM{9AM?%goNf1d!m;(y|8lu79n&vOczmaJ(f}~#{7hEFelMTW$iAbNP;OQ<q9=l2O8Xj'
    'I>R^F>Yv#m*9Jk$o1LbaAjV|8M2TyKy4x-n5)=jN%tE<u96E{BBC+e->|(${85A^T>4A3l3y&AynR}a={=-t3OilM&m-^OfTDoN|'
    'YRr)fgf5nbunIG^gf$wDw)~=YTV!Epu@Fvu+&#jQ!Z$9bKcQI6IZ+AyvHaEgCP6YjCcEWGyyvzQvR5tLY<T_!A8)K1kd&^okJu7D'
    '89IQi;1bVQh6dQ4!rjbKR0t45J}M??lQ6n+=VkW<iUuB(cfCYPp0hPrAnwJcE&Z}55r;C6uhQN{CIm00fBA$O{RepqUsk51%4S;u'
    'RAB&|@#thG%>bH=6VJI}VsYp-#~QiF=KGdvT!ES_c@_0`+LbPUj7MO-7q9hMwB=+!^G>EDNw5LMBh4(;v7*6<FO1YtaC73OUH&3<'
    'P#2{Qbe56&KB7LZKX)ber*IJz>l!x-pTrM$uz~<c8!o8$0#svZ=ULWLJ$3kKW($8Npi$5+9QgkN0bmt(w!+2SZrA8w{Q`@hh1;|Y'
    'V1)l!8o_1^)YT9)LH8h1-wy&;$}?);Gqu3w)&+TS)t~+1npYScx31Y{QbINZyp+4GDmP8PrPEhJD8N25VnPQWxVR&Gl((>H3D8)V'
    's#J2z0EtTa$Jb6)wo*OH3&3`7uXS;n;Agec$k5d7we^<#XCorB%&D7IUIbJ>-Y|PPS&-%Jbvx*i{xDPMeN8g6F+`MEkmrRrqU)*P'
    'D3QO|uX^tVko-pF{uPqwK@TbGmQ<ybbyiy5$_*6$D@r%ohn1dgwlV1PSz*ad@D%DsEfCmzd{IN%APuOc<`0Uzx$wDY(UOA3FwbD-'
    '!K&+rqi)lYM-cOcOjNIXC3q;eN=UeZtI7f2=(Wy2wgH=fD+6A6l(!F5nm$zznH!GmqqlUS+d*leW2;k7eGa<{&&XiZX>M)5-H6du'
    '$xQJw+#a3*gb5!<if<8Yu4EBBN4jrtRRqL`W{fZk^K>qovkeYPsy`K`IBoU0x4=7tS9KN#8TgLa%rB!i|L!G|K0g>1LB=ew?Kitg'
    '2<;UpRA!uL{!C+*Z~7@vc9u75nX&kjuqhS!vv-Rm>B8Qje!WgGd?u5y>2tihPK4glTu-*DNR^|Mndy?ZBCpKBp8w}hR~@b~Eg%GU'
    'brY({Gx~;wZ@hDo-l*cHO&IqTZ{e`h)<RUWxw4e#dS}8d`#f2Ec%+ei2GT*6x^JWJBW4v>1lYx6CHsG$ah?EH2VO$^0|7n^XpM@U'
    'mr=6RhfE3*B$f7`We1>-SIS2LAHrVOvM|&D|GT6TxJ~C&ujVriUXL`BDVyF|({Dbl&PMZbZ!gZAQKK(1e0QSo^r;az>Kz!T|F#eO'
    '<tnmT8K_uTUAbXQ@BE`V$=YN19CO{*HIY}m{ef4@R?i74&&L;d{Q13=88;<gyM9*vhy*t?>Q9K^+@2Zq_3&Oi>Bu3*<>qiXguz1g'
    '=a}aF(hK6GwGBXHJTg!y<oGXysydx2Wif7Y**1Pajti~*w8mmyX#0qba|BG8G=8_C&md{IK+^u{Ix|ogM+MGGTy#~WfI+$QlHNnY'
    '#9EKNbU%Z$VH^x9Az6>W3CUl)%AW1Ct_8+m_9!yEA~flSacyWBY4}f{`iE-2oT=%yrC-km8MPLeSlbAu=*@S!3>HenO@*w^<LZb1'
    '4i55BI=^G6&Qm_=G39bx`f3_DOWk=*>0$$ru)t$hCKKkWHEm-2=Tb5sy$e$W#Gi@;H#5SQ-SV~8t?Id3+0z0@AFx*So#^ZjUGOBH'
    'sv0!AGUF)gOQc&BVu*yd9pB}^NlQi(O$qtBwbLg@GACiwFmU=ersG$j2Q7_RH~7Ofi%IlnHGQl<tu{k6RFu9yYS^jMaJw@?7Zw_+'
    'w_zYbx4f7UBbZQh+)G9cT%HgV$vUR{C|<Ea(?Rs?n-Pt~>^;cM+2)CGzN5d<P{E889YIwE)*9R*BvuWHa7Y!W*h4`G4-4Dy*G>LT'
    'q~6a(od-7U!xJ|H{?2h&1&20vhY`a}7mu32Y9&8UV{ly{(S`B}r|XVk^>R6&W>%5+B{CCZ%>8l_6`4G3+F^Aj9MW<-t77&>rUp;?'
    '6;Y}+%DFqy`|I48@X}ng2rQ?7|8sB@3Qwh#rGJ9X-efL8RTzN1CD?|y)89Rh+$?)L^<d%D`EUhVNq!PZEJ<kkk=Es*41e`Y{$e4('
    '|G-MSU}l-zsDEbIBY>Aes2HWq=OZHaEd5mye2Q9WYboZ9L}5sI$`^rJZ`x#PeFXRf`GgFjMG^B?1#jx1g@sIM*J%@rPN!$gnz%AS'
    'gYuiB?jC$=!)8mKvf-Z6mT^ASIMxl^;qDc^_oG=UyY<AS$EV7unqYEr%0&LRQ1M0APXXPA{Oc_M-SZzN!V25L%1B3)g>Sz3w6gb?'
    'Wy*P}AwdDCMIY9@rnw=j2>IUxD0f*}+hO<n&nrKR<F3jq_p#?qOzMYIpuey&pCn`&)PNuAS(cnDhFVhUOA<JP`=NRlu$*)eBM^YN'
    'kco-`mso%J3OerX+@w3C*;-!Srv8&N7Q8E_l8S)e>34*AsGx^0RHCT#iM}%7v33I7LJn9x1Y!LOzJY}%<=PFtU27o$7;61;mE+2Y'
    '%Wze&>?h?T3Bf<o>21(w*|+)ww89|B%(n+LImdZovj`hpp*)aeYrF8%ZiXpU6iBzI_7FKx9J3|Ni@O%q%%~`~r5+%17fT>T<(70Q'
    'e$Yerub1!R<5ie>JaE{4@xi0&a_YMg{*1I~{E~k;m94@e+k`S#9G(|2t3u}S&*t{Uaa2-BZ4a8$pz7q9PWJG2E^6Y|>UN&<iNYSg'
    'rAjoJZ1!se9=xeE-TBS+9F&#B{SxjbIY4<T`R|+UzKraes&MQpbnWPFc{C@jaM!Ai$ru;gRm%ujXpa8v`nA|OgwV6_q#);nM0>*y'
    's-~H#)yZr^Nw~og6M>1EBN1?AY8gu3ji%>5ObrH!4vrfWmRfUg-+6S{LLcAlXUi|w%#$KD8G5dmd@mo8LD6meQeN{1C4^v?LreA|'
    '$m?vpx>fjMb=jHp4Jb~%IdzKD0dcg`wL}Z>-wgYB&pJFLo3*5j8BB$zaTSR3Us`1F1v|5^)vRO>l54K@t^O*4x^{a3qDo~A$)aSE'
    '^M1aL%cz(a!D_JT=8xB`WayL%0CUGErvz2Qv$b|U);?YT_(W$;15xK~%Y`5gO{UW=W=NrHa^b<K9$!Z_6ay&xej~!ws|GqPT|iau'
    'SdK^3^ThX4yyY}#nbrPp=$;_&t+=r(U8?4#+b&BD&J+8^K+}*&pS4hlaO)r@1i|uFrV+(>P=pdV4GX5Do}S$HKL_F$obrS>9TA#c'
    'GX|7i8T^A>Mg%-N(W1TC@P!lNMh|P7AZZ)$jSqX|%d`0r(9<(V0}9pC>g<pWpLp<~W<xQAq3(W}r!h2@;|m9Q=CSR_N*_>P)vSH1'
    '^q87c`#D;UWX41%cbdPbWkQ2Cjip|wg7P$%BILa%|NnkE&am|2vw;%_EQLHLA_|0MOJ5Pp7#!!JsVa@nEV59w6^Ab~4xCiqB8~Kn'
    'B|O=h00DXCqt1QScQ%Vg5gYjCED$Qmq$a4A1c%qD;B3lhAAp5kbc!OH4FBzd$FESDXtcF<guUw1D-PJEV)wKE^}nDD6JY}3WzM%6'
    'UnpN7@v;WbUYn$z#ziKpy$IzpM5l@vMIc^%{O@Dp+M_1{mrzoXUvZ8xvA0z_aY19xpq#!arSDR=o44KNlmF*OiQ?1Q8N$J}h4^$='
    'oJ|Ws?MGjg(kXz)b@HRP@11QC5KZu^T?psRoOr4qR7W<8eaaqh?u+}5%4P#p^df@Z4g^a+lW7^a;#<DvBlGJqEtO7#@zz-;4<m26'
    '_4838r2eFTp@7=1lc+L^Ottlfke4^V<tJG!ItDoTKbk3JSh25iD}yx&9>O-HoS+r4!KNMJ=cjcn9=u0ecyKg=+!*ts+gdH>B3_R9'
    'z<Fn6xZdFJ{%F+NI3RyDn?%P*G-~D67Bvrcc+=FHx@Sfv?tjW55am1A0$nvlQ#wb>KN04gp~<Oq#qCH$OqJ=aQ-6v4Z(i>$Yc$f4'
    'nEq2GtfMVKLEK24iO>RU#Sr6`X<M4uZAbHlh1#;V=u2T*S@OhVTNROG&~(yX%SC}TlloaJ9cxZ$T~!NAX7tQ9z|QSo7UIB^Zyqz;'
    '|Htp{6tSSYYIfk9Q%f9smui*i7u{kKGVX5z&vkUm{k|hV@Rn-tGvkH5Mw{h+XU0DbSK6_dK8NxkIwAl;s%>=z^ZAE6|9>XclfY|R'
    'eba>ToPzUB8xI@6`|*FJti(*v=<tZ7nTFF<+%pdBj4Bk)ux-~wk!7hO?sPETx=^7$+L%lc5EeU2(zoDf9^wxjEI#k~2JLq)?W#wK'
    'Q6Md2CskU;7#QGC1|&ot;{NAF*<B+3bk#u)M~;tr4m=P_Apk_*YH;GNfQOukSo$?H^-TP&!Nkb8k@x*a>4!A@j%<uJGgyc<?idZE'
    'Gv6F(u9$rYUAhAdng)efj_bH*0-j8+Mvw)AEvq(O;(Q~Ul2el}rT_;$JETj<IaKC^b4hop{(i(Jl$r~`&u!|YT*^Y6Fsf(}uX#Oz'
    '4k-8pAwz?p8`c2aivve5M}RN15K~dlyqrA?Z&-vz8VMQ$P+wO%1W-;RW>T3~m5KIg5EuLDMAS||^(fhpv<Q9Q(WVW};DuJdqCOqI'
    '2ytqz?%3>G_z)l>+=<WgO4%gbWChlLWssKGmv9>R>iyUT&33CLnSN64&8Q;(gnI65L=tM;`tL$^C|B8c67|ALrZ0fCzc@q|t@~FZ'
    'jCqGx8lLwr4TB#^|HF^lcs#(+-cqw+6Gk6VD`8Y`mvH^+JmRlqvSj~FiJX~{t8r@E04$xm6)iRQ<<IWMhZHKnP7PNBnF}-Mhw;$$'
    'j*UeubK4w8vTwG+M<j)5#i9z?2@-uPJiQM4(jFZWSnlOIF`{j+@<KB^AN;nWqrK`-%C|E{L(HSq4_CT^vauUpH=)r3oU~BiCWs*b'
    ')aa^1z}%Tl<1*Mjc>kxt)Mug&JOQ5Ze+58jKvtYcmST}x%_v0rHg%^)n*fZg0qzlj{6h$jH6q}`ro1(*lXbZ)bhuE2s}`g}%W9fW'
    'I@3)d%yty*Gu4xBod%v$;i;ujlD>#~7qav4Ozpf0L~5bnIX`{n*c;nh5z67MU$1X+O^#KLhJ>?DEXVCp^nG#aT~@=+FWPaQ@=74y'
    'RBXW@MdJmdq5>bhmJuM2KdZN}&&J#$Q}qvAo$!R{t#{e!7Lv#~7x10U9KH#&(|_OfQS8>PjDDv%8ibD_<SdV(r|OX7DTDDsYizP;'
    'Y4O-Kk{9@s&^5+}abR*9ym7c-+Xa#$bi3_PK7;0vUl-=)F`i^qJglTiI7aCH7|)+&T?jjYbrfd@gfdeSF(dPJeOITQace^v0{k|e'
    '_uTKx^%P&W^rHAyqy1-Qi;Q;u#PZSi$(S<}7*0%&4YU5fwm^7f*u$PqI2;YwX$%Sb+st=T%2f(Z52$B5CS?VUniPOoJfoTQm-`oc'
    'glPa~lqIh4mNodm2>9gUA=U#6NTo*KNz>R;`@1bIu9dO*<l#gwdA|Lq%UJaT?BRNSu0SSWb|+gb{Sk33J3@oz4AXi$0VM8%jsX|1'
    '3c*xSAlZ_=w7=QJ#(Wd^K3^vjHj_Ii=niE;w{#{P=?4UzC83Wzn7NR^$dxz$?zEQ$EZ{(Dok#UQ777K<yY%;yR3QSBkJXOn+C_jN'
    'S^nXa;<=gz@}c9$h~i!Tn|gBKwK?H1As^~U{BW>8Uqb$jr$32}XtO9vOjo?r#iAFEQB4GaglswF<SG5(7zgdYe4D>@bNpsuuy&pT'
    '#6ptCBJfXrwqJ2#qJk7-#P%J`9o<LcW*!{^-_+Rlmo)XF7;PPQON%Fp6oT->*o5}{7PcXn_az{lPKoc9=p{i?Etyxud^C`aI`*a_'
    '66-Ksis<hZcZ@rCw@W0X?XJ`;!UWcKDsI&)j#b_|PL2OWr?-*IYNLfXxZFCko2z}_xT@&jEiopbWp!elj4A_E_}aaXVb#*qt-#9a'
    'x1dnbF`!d9b=Z*jWT0etKZsOK<HuWhhQH$Xh6?nqJ4-N>x2$;&DX9+wJm)ahBR*Bn9fNoeBA-YjnW4$sBq=a;8*OuK1?+9+VmE$u'
    'Wg>uPLXWc4DhAnip7yViM~NVgShLViQKUV;V1c{BA3+7_25r|p_<w5phL1-_PgKnCYs7~CDU--*lH6Vb9Jfe54)wRLqZ8m&m2RI{'
    '-jB|p(%XN7Z_j-bG1{n@v-tbeu+~vEaiNhMDXDkcL^2BUm^0)w4|529Q86AS#-Z)b>uEp*cXrfp<d7_O{CzH*H%v;_eGKn}F!Ny&'
    'J|lh#W-m1#M{5``zp5f0NWul*I{nRf5gYjcg9-zmFkDvlG++{YQX8FE#QV#>8Dt5MHhOBWir<ZI%ASmdf)q%-I$Di<aTXUy%H;vD'
    '#)`W<^&%q;h#hQ#o%E>__vvE$-+{ueZOMECo7xbtaVX&Sh|!Sb*WP<j65_DoQIC>9z9fgRL!;NhBaV@C`)N)|8GToQXqqMvS72?w'
    'dKB7jfrfiX9_lmjvc_<XGqd0nObV)EOfIGX&1tZJ9$jLR;*GaN03Ti=^qR(O%@0N=73`C0b=-SSkG>y)waE>i;<mVX-a~91NPSJg'
    ';MZ#5#m0O;k9dNfGc8rfyknJL9|FrWIffYK8gu<3&LFAN$$$>#+d%557;Ze;eLQs7J4>;=UGA=LgrEq2vYU2!N?mtylZ-1&%pAO*'
    'T>E}YjLf7zTJg~rGk_Oq(pdXL306cDt~(5v>=v5WA_+)5^*O~rg&`X#_OwWYfN)8rtB#zX=J{KUmmN`C%0pIUc4&qN_h`PU<wLgf'
    '$1hT=eH_XBJr4G$z?L$2?XcURwY6Md;5Z{n0r^3>O+kU$`iW9^h_wvWZ@QDPbL)8i@sFGnJ^#^w{tsDsZEx!XM>9|6^PDF-=pb?Y'
    'N08)=VzW$q`P2mJz?hX{XG^u_0f>z}-qgOKeiSRR!nhzm=KN#%7!)~MVsht~J!Of1?n%L7A^{Cgdi?KXW1rZI%E@`$cJ{JfXhcZS'
    'reG!zrz%m!kfRKTb(E0bMv5qDD+v5ZO_s?E>SR$Zzab`~kX=sgGZsBHmY--<b^NL8RK3EpCu5~(q{F9au&rgbxVk2i&+C<+`%7}1'
    'fkHx8p2fN!4`j@^{eUzguoagA*55<P7pQxCp)IHc?OEDTPoBX*<Rhd++4j!i?i#;Vk}rIsMW6ngwo8k~mdk`%V|Yho1%l2-klW5L'
    '4-9Qn0!<Ii<S%2{*Iv6VNKHWpOM9WI;uqJ_C{(oI=brNYVqts`Isd)9E73gxH=z=>ss*AnG~eHHOT_KO+G70X(IEI&w6{yUS3<B*'
    'U@L1NP^k;|!elY-Mge|=!N%4`8~1(dtMA9@-`j46JKfDjG?4r+TOekIFZjzy#>TDPAMjz3X80QREbZHD;~pWI-l-c(MTzsJxZa%X'
    'huFo8eY?k?(K#&4;D6|z#EaAy{vaO=r<LSVisdc9pF^qh#oX1tb|eMXEqmD1uP6yTW9XH8eJ=VIXog#$QelLoHW*Px?{s1M7rwS0'
    'wEmnb7`y`;YLJI><8b`|;m%s^bfZWGW*maJJGw0Z?P&F4oVveirOGu6V5fH_WPnbK8D{h*av@u>+_S=M(n<MCv-EEgayM}W!6RzX'
    'cGLRjb#bNT`xlRWnpR|<Q`Qg3^+YF=`oCeN<-)cpZ|O$O9KjUsjG|X`T9O}9UVE0?_X+P*CHxe6AsGaWHHca*&M+cb+bf!$!&yL3'
    '9MfGbow=Xvx{~-UVvSs9&u;{B?p+<P`E)XSG3s|X0eCmDx_ifo&|y9+!q=lEue2%vB{7DhW%-M&2q6u~&Gy<fBw#R59yPVB)K3S@'
    '^Z>e*P@T^9#1@{`9`sWa^iVuL4P8eEE~gwPP}x|HN^T4Yhfp?7I+rI$vQ$zjOooD6F13~Ylz~C9(lT^(9OYldF5}-0QzIfsl5zJC'
    '7p^&2c;8v~4tG^NKnN836tRzS6@g*_^$!R|W6**@o!;NHEi!kdx8txBVSe##-4wEZf2$5lFgJV9j@Zr6u{L|NW&;g<T`Ic7ZcxI7'
    '8N2$Rs-UAb=R_7EKGJ=Sk-*C<S9PeyzYzb_Nqy(9>vFz!iP+|To@&Vz`Dfgdex?Hburw>vX75M>iR1cDBQj6bcO&fOj7jSKWa5r+'
    '-Kt$KBXx;RsfT1V*2%O9!f8mtqLMq5_fiYN2##I;N*N$Xlm3gyZdS?v=b#_(<?JiS%i9~M$I3a#+x76_)ky-k!MNe)re*Rw-(59W'
    'FuZAS!r9m|+PZ<vX%@zi9tQ`vC6(ifMfGFH+OEz1$aPrd+_bNMVwhUn2POG1HU&4h4Z{u~+I#yGy9z(k7P>GvbHUd?EJ3{WCcOis'
    '4n@`a=)4NBa2s#<SJvF#L`A&kR#ARp#|h5yV}l~4jrBIGHKzu?0*t3T<y3pTG+R{uPz4Z@?M_c9cmhO$wY6s|D>B*Fy4LmzBuH@U'
    'Uu2d=xvzww(V%IF0Lv3iW38Qr#8MP0XEBrUuR8*j{)t_s%S^RxtSICrcX5^|mX>zuQeCARYbZ8jE}WB0!3yh#mA`A>P?;F6RF=DL'
    'ebd$e5UNxQR;v*xn_htJ%#Qrkj}J4$4{`pdt{x$H7%=3@*8`c_SR{bW?!sU9S8MX0xB@vD=E1w6?iOfbf3hjx`9Sh$K(qR9oT-#f'
    '`I9{(%3b+Kg1S=0%%e70-JW0(2>FaX<=ct6&%7vUS^X18t;Z~0^8t9tFlaU=qAm*we}T%PrnaNbolSJH>2o?*GsK4DlHIW{!CiZK'
    'C6neVo<t{$HS{#jV_jx?L$7-V_u=y-er^cYBy!}y_rU9cZesW70HBB;cp^ymSzZtoPUg6p3Hkfa5;UyipJ^dSvJ-oMd6~JhMKSC?'
    '<~(eQ0<XcDl~1w_c^DPY*bsb*4M6*{3~N2GUno8UMn}w9;CppJhIX~`M>f`d9RTMtK(3elahL~YrVlB-TuEP2?s8m$ce{9BA;?|b'
    '`#{v`;N|4)tbT+6CQ?75R|uBZFnU3`BpPJH0S@3`s@E4;qKr>|QC~O&w=Sk;(4VnYaUb_DAH*+pZ!fo=$Inc_CBQ<^X;7GO0-@|)'
    'aI=#@`|jPCol@^@(7qIf{&AagH_#x@@HwGAV578}V3*3b;SF(^@zxsgsequ|$Z_1>^+KSVXLMZTd;n<!kHF~Rz85y06?*d|s9vyl'
    'E>j%yWDaR9aXQn7mW4VR^jkq&X7b%~_x70GFHOt&*|6$`SV@&~M~?0W_8zf9unQ0j0JMdMIQUUx0&h&u@T~JfeC^_d=Hdf{yJg;B'
    '?f7do$bZ`=Ti2wn-}X6HA>R)D+U~!qO%sA=qv@tkuDCxbyJ5c2!f=@<M<*9_^gC9>@YN-}QT9R5$2P+ia8=0zdeuU0=|R9w0=M$}'
    '#o*&8n?Z=L0g0>2(#|Jx%H~kqSlUCWF`<$wK|1ula`)>(Y1CUHri{#hxaQCAkMElJR6UFW+P2m?{mhTD-qUPT^Rk!7jv~ygV}|!F'
    'bUk>bOkt+bgMPbLUJH6qunre8%5HHuY(M+srhsexgSh2`Z9%UlUOLN=mpsXD06_XNi)<aBP{~j%A(A}#kkI(u;>OE%dNdZ|>JT0C'
    'AiSi@OUKDH(ILySY@__sVn9wpahymFtgD*+yq?*nlIMFgH$wEwI!&btU9c(pf1X>o11{H-H<y4k^LUeS4)FSq2z!@Ixv<)sN*RMj'
    'Ih|7R&tJcs^8Ys-PoS=u4a5KJ42eBlY4eQ}(;8c?6qscDsLo;sPqwk%U&UdckK%l^83_!-rj<`E!#X!=1$x)kc>Py=4s#Ig)f*BJ'
    '_izIVrq6gwp_ubM8bhsL;qn>M>u$C#VZ_(oiv9+&pK(gSn$88Eg{Kf9T>0%BX;re@lDqH?K+qB|PHGT~k+bxznJ_akM;KjW8fK^i'
    '5IZ5<A?|^kqY1~(_{vfEd!qVpeU@(uyxO)-yfixt==$d_(@LcUE}ZH5L;kC=W_d+66r@73rC#ptF^ApU&Lj$v{qwlx5n#{2!FHTK'
    ')MR_|Ll-{H*Ghn0g<Q_<2}8mc8r@Ipwc4VAPCum>vCTzTAYaqTp#9$|%!hg;KY&T~LP%9a7rttZ%6SESCy4;58KKbrjC)v=mN~0y'
    'HAun1)Lq8gCOf~Ul6r3{<9!Us*Pb#|67jy#@<jO3m$$6wPg6$wL71IT5Okpw3$BZ479{7mOuOVT43wJzM*z)?WCAn{ow~C`T9*Pg'
    '^X42kC{T=AB02vtUnA57q>>cqA8J3W40Jnf6ByPT1gkQ2jr+D~g8k;Y_TYsh%C)Uqe{kM!Jkgc<`-4vYkTj=<gc2?Kx`OrZPc9}o'
    '0Dxl}pJ9r(f7a_!kcf6_R*+_rn!nzaSTr8tW8E<R&KFkY&`jVgoU{Rx4irft)S3}0hQm2(7*6?Eyuh}zOdPi7h^mbjuJ3IXhMTvH'
    'jGA0j-Z$iA*Dugu=|A%n$bx0S6Q`xXv^+n*i`1r(<UFwACWr|uOIqk3(VuepVXh9i^Yp{q*Oywsb0bJ}80RpbP{vdyzg_AN7O%Lk'
    'ZAR%Kmd!_4m>BB{Pq%F>S%r6SG)zbm-IaY_qBT=SLA-Uwh0*}I$qPmIUuV`Ry|s@sTGYu9LL%YTw^uT(vH>3HPUwe7s+b~EUO8k2'
    'ygc|i)B{m{bq3Px**8A>DdRD!@y>*ov6s&W^5fq3(b^|{5JecNj`3YKbo?0H5+UA60%d1m(~pV+`LsIVf_jbgooS!%_Qg0f*l6`2'
    'H5>t?S6lKmzBL7cKE^ZCzIxA=V4h|c&X{7;xkAio{-Ex<iKD_w*7rmRpEYohs&rI!bFo@#HBP}Fi`wX%=Y;Qp?qX^|$N54n-aGE='
    'D8v{x$b8|vhgI3sV_CPV@Q&c?K7r%rBdc)C4OFpe7}9jD)h#hmj!oJR|Hxr_Oj|W&%kE@%H3I*Q3kp5YC!TdX`OKLPkZKfCe{fU1'
    '!#@PO@i2)Wv&~&c%>b6~sT6h0_gX%alB?&g;DQZuO4#U@tGf#CLm!7Ns)KmHuXtxlePdT;Uys$cG6S(ULj>}$5~2FD0T=7J5@VmE'
    'l;)m~`LP%mPq!C9JSW+i!Cp7PAtyzp9fQKB1m-|3D+<7;lbKiOIl9-nrRdP*iM^^Uwyz*a%8GNLQfSQ)1ZJVG&*w9p{ST`qb^bu4'
    'gBfO*9^y`8<yUEkMtah!VA+z#$sCE^U<U@1h^vJY3dD>ZXi$Ct7%sL0)X_t9GTYmJ5jGz}ZD^*6p1+NRgCNV<$Fe5O8;c_QFq-qd'
    ';v7YpOtdH5A*HN8X_ehBjnY$XA2>NT6GP8ojOn@Ej99Ff3vgs+-Jn7qjkChH898-`GY=J5Z#={*l&+utuuy0HjuVIp0kIpbBX!bl'
    'bDNyydop2VYp+tAvrpDNq3o(u>jMa(e9G<1Ox^afEIM6&_r%RCF}1S-U-nEG(6`mFu)5OE!w9=swIE`0a*Xt+Jq;fD3tMDU<-{FW'
    'i@ownp=3~a$p%k~Gc+@_==ftBkF=U{c8ToBAHnV+_wBg&&Q`9f1LWU%N;ddhOYYrZp?ipTKk5Llv?5qzjHxy6_+4*Ap{#O1=N%Oz'
    'iOMJj_%06ApM&Usy<g5w^G9FJ^X3`TTh`Uj_>t}0j@@|aQJU_I7w(FGI$ga#rbtv+u)3t$=ip{t0?BF7f+^SU$%hXduiD>kkLDd5'
    'VJ)`l6o=Q~+K4qZz>Mt^JZYRatggMW;9_iu=kh(!)P#Vi=}u?BjSa!cPoRKqI>7(%>iq!k7cR2Nd@i<leGJR;7z<wRu&Lk=MZYL{'
    'N~JGQWY_~xs>u3D18qXzqYf_IJum53V))aPE<Qio4&m@FNhidvI5L50Xu(N`khEW+%CF6p^CTljgPs7}vdo4DFqA%(plkW>(p?zZ'
    'Gvj(pzC>S!><w#}A<qmk=-$oh?qiK-yNm?k3RFhC(a9AJ>oV2+HD(Zn&gmRlHQD`s@~c3hWiVEWW_Z!2*tuSPhcnru`dDAPUcguR'
    '^8v@*kO}~GPX#5{<cD?P-GO}1IDHK4LvhMclY6j0ypzxK+sAniE^UJMdFO(f)hocd5?nAJ{Cl45sWEDZzPwdD3hWU`dR8jsh8qWH'
    'tQj)}y8mWYQC$J)_*#)!hT`|8k<@!Z6<g}TbE7X-$-U0*np?cZhxu_Jhrw8>f9W6Khq3}POK?@iP*G&dJZ9`We~nr@_)BCIVwW5q'
    'aRyek1ZrNjVB;>RDTnIdNa8qa9&PT)W`2~EPbjjU568K3y`&#J?3+ZVgY7Or0E8PCpSj9u_gkW*lh83{R8J4J@I$`NeTOGK8yd~$'
    'nK@~m`VMRl=1?{TmDXoeakQqXy?ZCFn=W0x1gnlxg|-EZXix=Q0CJm$-pF`yhHc*m!ZJh^-n7#`)`vRU=Dgmsg~{T^x|F0KKIU${'
    '&4Y10w{>`JK9GG{bN2UJmj>ewhd#Sp9VviL4KuC>T5+P+l3ZuHwUZF;E(E}`78ImRgUaJol(xn+ceZ>DN*38i@M^C5QszwrVZcB{'
    'g!}WA+=E!|?wcM;d`ERSrlU^al<I7Ea~Sok*M>F4vTzj^#FD%0E?25R8K~m}6oL5pu6&F{v8I^BjoEJ$$T&CT3ZvD;i#Q5+5ON2d'
    'lIb^b8)ZJYs6D6bIM<%NQemydT35LUbRvDbW%!+Gryp>fIYTFW^{Z*DaFFM(u4f!)gUpLUvhHX?U&jv_2zffo=4jaV!GZNj#1a>$'
    'x@qS3Ljv7sWTdQO_y+#_h?o=3i?pjbtee+!f>U0}4fhe`J0nU*bo6?tcj|f*C3@yHJ$cJ*s`)=2|2#?!;e^MnB#6aougD6z84p%n'
    '0`J2nnR`Hp);T-yx)F&3w2sq0g2KNk&?BOy2omgA_hHXIb+;J-|L<;tL&rd@lXIM1We5N`3WMJ1<vthT*ig9?=RnQ7rHQ^B-Y&>a'
    'Qz7eTJ$LE7a6XJ#<sSo971KPuN#0l`lts%HDJ=kQDqUDMx>eOyz<TGQ30i!IIyll9Y^T|7<winp)V%rvlrKrROjZt}`RD_=KGJLW'
    'e01jAzU4}BB>Om|72uwd2OfmXX6c9W4Y1`;WK(?KO1Zs~3oOi8YB?x2pF+o!Ew`OT4^7$()sk)u@d&CB09c_-Ehxn5Jg8hAZ)X4|'
    'Yo3cGK1TE*k0bxtuH73E1UvnQ#bIs<ZhxR_W_*B^aUPqEP6ehwV*<at-1M*r#qk#&CsMK^8s(vC*5nE)*6@;;YMMi-G5mGGb*n&@'
    'Ug{W;fVrAIF_x1b@o7X2>aDp@=M^#XP}}LXewLQkynIbW`D(urT*>r}C(J9uVNoKw+qM6`op$}ng@QU>&0!nR{o5{Tw_2ZwA+9X>'
    'qrTrM9ka_X1>lROS&S+NBp42b(zmhNSJR*VpiBk_GeL(D!Tu=qYkp&#ip9U42Z~297cmEnvhI4*eiQvaYBU$D&ET<QDSlS&9qX;('
    '*3e;<oY8)>*H7D2?uS42(2CJIFH16*s)E4f>@)OoPBSQmY+cjbCoaLh+kC$h49px1Bf33E77fLT*sHs9?F8s6E(OGV8R;JW$%|o;'
    '92$aVy+Dnw#UI>kJ8_5D#G!>KKCNu8B7fd=5!DlU#Z;dF<ux6XUV8nWxCn=|(lqN#oJHL+)cd~z%b!Xu#Efx+ik8(0zo-Vc@`J+|'
    'cC@%zv2VX>l3%7RH{w6^*z1SyyFmNVO@(}`<&GFQ6Y4p2{<>cpwyyC-!uasE*PuGJcXjVjF)ax}B5em+*H8IQS&*1Dz?63lr!$3q'
    '8p6&hJaNL@<nfE>cD&3VGc(X01Emd~MYK^|WI$;`QQ)|IInTAA0t!-TdqCUT6NgU66FxJzTq@8SUCEpdRUbkQvFyO%1ZR@+6cTg7'
    'pBBX(2e0czu8~B2?Uh--4MmXREWkZuyqer{5y_nJzg*Ej`g_8j)RuO^AGi^-NUTE$-7qrd^-r6@+&K?pq|;mCP12KN(M7)^BYYVd'
    'U21MucY|z525zRb%u##qr_Qm(kD`-YE_nuEIU6~Ia(T7dB1eWZeGbTveb@`pG@2&6ydMht=-vWph)}Su2sMot?ZQr5Bk-(*+a%qb'
    'R`PYEmGp$1S&7TJltoHi6l7O|qoDS&fw9D%Ag!HjwzWT9bNjuoAU*{LN=6ff#VK$dHk9WAE}0H2247Z{T0^(@C@8pKZVV5EdRKM}'
    'HsQG_S{^W~OH3$$j>V1~9&<=Qa(#Bp?&(FS%Co=;*5;S8mx~=~n1<#5cDT4unh+7@Y-U|_B$|n&7)Ue!Y8Ak7sh(5XE%Llu*)!&$'
    '>JoK{^<z62R+6mVZ4D=tqHuy!M|iY);eo@q2@YS|bpl8tIzz?*9j2_0Jvbtrwmy?nG-%n|4@#)Ff!a?Ft=#L=Ha6J`Bh;ttDmS(g'
    'vCpcQ3Y7oT2D?=D$nBJ{@m`pBEf!_)6FYkvw`)FBwMV9Hf+;3{_`zhzRzRwRC(bAWjw&i030r=NH7)bKWyJlE%1a>Y8}0K;b$<kq'
    '%H(Pa%~~-rq-)IV5!=7T+hAp=x(u(oLTiDk^7Mm#id5`cyUHk4Pqo?IqF3yE;ElRk!9P@D7)^H$00?0C%b=h%GCK(gUKIF3{gf9^'
    '4fjwFBRA394bDZ2m8;4!a?x8aX7X6Vxa-&F?Z{DwpQ=oDJLpGG#Ewi7by58u?mkrhf9o%@v<SB?IYn%fYD}R&CpNSVurWAT^(j}V'
    '6pcV$hG2G?A2DLae~w&zp0=(HpN6WfG!6X}aG|R~zRJ>58d;fy#$06Z_fLXYUyEU7KLiiTwj&Tt_xk}Ws|v)tC50z6Q`kG~rFTo4'
    'Z<}5+otFuJfF~5rN4VVvF+OAGfy$^byF~9S68fDZVe~DwEhq=7KG!S%fQ0UQLAZvhH<2WL5BB!CzhJ;?$0}ovqpgw{1QHHEF&)08'
    'i=h6woZ@I{90x>UMnT1I@T#|WLvv%5pzJO&kCK~J<y4D6uoyNk(4q;3Jy`>fatqP&PO5;Z1Z76=n@;&EOBV>|rf;Djr02ofp8+Bp'
    'iFp(^tOz8Wp+V5Z-KU`8=_UQmgCkB28yLuPa>^{A;r7ROnF%M0YBH9I^!!RZQa59;SWWx;9b?SEz93-um`dq0fTZ@eq;#dOoA|!d'
    '=lSdl5oi3L=My}|cM-eR_RS(U5T1<NbO%8z*FP60zB4_XOMx3!Hj*dKalV4B{pk7Rvws~U&Ka<pu}{v8r%c51kb5~+9snsJUZrXC'
    'w>CG!SsD2rg2*`xI3^nFKe&^%>^v#Z{%U`1rSk7a6!#!4B)g%uYin)tY3I@g5rgP+yrE{tC4M>uyCqxU7@~UKcMmnlopUeGQYKwd'
    '=A+!L*MMRPjWa}TfIRowTR(JB6fZ}>B41QvhjSU80+=V(=6YEoe7+Q<Cca}}#FBCFcMf*D`0_+#Z|c4+xT_B-RYOf%Hkw5Jh#2fv'
    '(w%ZJkMtdyP6p7%a60}E1~PuLA;ctLUr*tSVW17Rv?liCF<ZOgf=M4CyPxKh?&6v<U)6{ftC03Z+`!Yms=)I2u(N>xJD*&G0yM=g'
    '%zv8HWruCIPq(+Unaf^fS?MKPSN<=`qc*O9D4P4w@)a9=nC<R6>2<hm%mgzY;wh$$%l$8HIgQL%x{R(h*Dr1i+r9HP;WYs-iueop'
    'Q}xwDCX8%w5K|iLfkBcOwLy>TZj3XuwV>i=8aDzxJ{|v&VL>mY?u(n)G#f4QcL(8dgor;c1)xPcyzc8fN)apKw~?(HdvT}6Gj71i'
    't?k+j<ZA7xgWNvoVu<4E^B7RO0p>4<gf5~Q=LiN`Sf8##jeNH8n{)uv>)V&bEu7$>U-l<_P&J#WHn58C&3Nq`Xpi!o9b>%h{pKLU'
    'ES}548#H(;zSWny6a$^SEUe5l1|h23YP8*!wt+eagnS1<zpHzdb&~QK=&8Aq2Shnj`M4AyWBuDPia8q}eB!6GyX!s_8jL~h049R@'
    'ql_AdmDey&mKJe^&drrzHRAwDG1zo}oVGdK;V{zl{()O_)w=&cnja|)vN$JuMg>#K$<cUpdil~%3F&@{@<-7P>M_;KYB=?xWRJuW'
    '3GAfJgoHZnMhN`xZjM&Dq%aTbMQokH^1!+u({o?sILC?Dr?*}iIMM4;>z-d~t*vm@2vVR0os~Y@+B)TuMMpL1R|I_Xi*}|UoyEkI'
    'm9m@gG1%K;_*GnDzC_A8PpK4OB^g6gB!n;-{oXU*MW3`_6fN6`e(N1%zsP`%iO+-tZn0vOo8O;u=Yseu$F$KB2PS%4=K!p%45qB<'
    'N7U+L^S`C(GfST;O~-4(Cj6Z6W8pmYbf!8o_gh4lWw*wnY0!n^_g^hv)Fiy2D%ADV1{Ha_O(+Bg=;e^s&vwF-dg>V>u5qdF4u43^'
    'W^*9m4PE~X0R2Mc*NS%YiMozaTKvN9%hHHP%w{?pkC43fc4)|VxfhS&(;?X+K-?1;Tg_zk<d@_6c?W=)Xp=>=4Q{mp9bLHDVxzqs'
    'VL1itoC}z7pP5vz!m*}mU$Z=oK7*7Sq^BAQ!?HpZN%^c~_Sfe#CseaIWE>%xqzmjn*%xhFOumdlEo~IO<)x!A!IenU7lXIJcBk~*'
    '1YFwRk`==C8=^ys#PK`zSy`ud-E6ftY_>D@a6OIsR1oP({XWh5Go+w(9bRL|fU@vd<Y~GX3v5f#I~Vs8%tf|aC;zkec=d}$2a1YH'
    'ihnKZ(KPq*dn_id%i2Vy5C4a^z8q=mH;e1l<7E;5l5mF_P7)FG1P$FLH!aYjLeLD}-k1+HOcpe<%`4q>3zoQLbE=Qp0}h+*op4nY'
    'eD;d6&UC<vebsP~%wWk*$Wjz+Y=c9*%CerKyK0%OjWffzaUBC^Mubz@uv(+6ZOC)M0&57uztgosrvs2q@WHTas@2ni>*t@D*G51x'
    '3PuQn$t9nf&P66z(ic^x%(IcKPI(8GpsA&x)1oel(G~Q{BALF|_SK5?6Kf-QJAwQ<L09#X0Yj-p?RRN&0V;{i7U&)e9>5_@xX)YO'
    '&eQ4oVwsF0ARNL~+4j^*Y$!nwAYyhmW&GK<tx8j&>+C;63Ibf+zSvDi+pB1fhXR4WT@N)r%L%>^x<V&+Gqwxy^s*g8D8B<IOe+4n'
    'i8=p&s&Vi3iWtIOm`uki?LU6dG6s_+W7R(rO2Q6j7##6qt(ZsNn}9596b;-9b?$9=w3N=5a7fynbtV9fLC)`sGKzY1FEVE*^@v4P'
    'Gkl}CmjPum$R%51vhHs3Mjgx-n_cW_%3RC4StE*U^VhMw-q@?@{eUqVA^LL%U5ao@NB{+pl}@8q!?m_0O1#-YhdbPndBqv*$@ch%'
    'f6<KCYj-pusi(L~8Gzt6+_4y?8^LX`ME(q=BA$$!0-*#M5%*o=B9-2x80&P-f&bxp%b^x*r2pt_;u|5l;(O5|Yd=0(R{=jY{yZ!+'
    'gFnwc6&6z^lbW`#9T+6KLbD8Q(E=q}$5!o*4-lWQrwJyNtuEz_-+VF7Kg`bl@Fi1_X61PZvFqxAs%qidWgj7Hhl@~vgsLVJ(EAj)'
    'n{}er0CbBMy>d$?Am&aq&rTiD>*DeRdJOhrb)ZKmkke|1XmBas;+B_h)@3l&f)|y;tJe={-m!2kGhnSF7T8p4+r1CIvrZ`fzt?#-'
    ')Lsyyl<ol{CatchudFNGzo=uU!hVpl?q3H+Uv2fiX-|7mU+j<P)i%qjP)PZgUD)UP^JoM#ZmEl8)x9n0Te<wK{kd}uxVY`G2dMFL'
    'e|WSrn+m#ta%iat*3N9ynRYajsR!F89jVgl;Gdgj*e)*zQ`4U+3pq{YFa#5g&w#QT*L6d*7?1DM+t)CVE~IQc7mIOU{!x>F(zx3J'
    'c3D5SU<x)C7Y*PAUp1$<A-k<VG?36KHI>?-U6j>S!t8eUu6D8UQs(8YeC;5>=pQ@~(JPxT>3vJIU0$RKxO}~bSUjw431=ewy@<Hd'
    '0S{aQk+=t1XH)#={yt?R6fts|Czugu*rWOFsZ!FJVl|q?k7IO|O!sl>KjFUShTojGf-Hbua!zJ)i#sC&#{=S)iZ6v2x<os0P}QQ<'
    '`U(StGI@;`f2312ua}8qc(c_cR|SVQqV~#4iFTHE{hS`QcvAAgcvxw0xNEs+@>}FZ9}e+@5L_DuerCw5--k`jo;uOw{VTc}h;!`h'
    'bJ(TZa64y3nGy+wE3>10bkY|jTNto(C)pMBiU8=MckDl;m##*29BP1_qe0B!$824lZ`uBd&_G^Qkm<O7dIBotmoU!hwl3>)>Y~;&'
    'Ci-OM@2@}9y|=ox@9VdG%&gpe@{14^{*2(v7X)bc3(uC6PWxED1nj23=jEFG#c(JH+V7#0+?+UvGVu#&Yzqu3z}*NkL852aCiP-^'
    'O&fi)9R&`YK~{>-rDvSxXXBxKdq$JYqeko`m{;eof3|No6C^wn)0^=A?F#S(%0c}IBPscsk3TysL+VKpD9+IJ2b*tER2rdodkFC^'
    't;bkvupdq00Ra}(DpW%a*4`JAXwPYI-weXi@6IqqC~GPRNU?bHL#oin^CcyjWkGyjPKFx0;O<)+wjMduHc*p!NO|LBR1Dxv&L#||'
    'LDFo?t#n}*yaN$R27HUHWOTozceZI60uc#%GOSz033gkiPf!{0;IC9FRCvE@5YM{9BbFDk;gB%D$|=`(6lrZO%&zzdzCobC>o+EJ'
    '7-P%z0$HZPmL#uml}L3VVh@71eq<s1JTkK|jsnRtQlt^rNI`70)Lf1%dWFzjLaGl^+Tu|FRiL^n{I0QGRK;~q%mjCEbcN!16-`<2'
    'E<1g~woFwSixk<O1c8gR<#4ISy^6mC=T5mrqBh~j3rS+Dl8|CeLry=#Xjz~RB-SjWi$Q4k=umiq(^`jv1mD>HBth@Q^CdO1GC8K&'
    'Tsqh?fJD3)?#!Xv8T8m+LD+2TD(zBntXEL6>}ba}x9Lh{1rkJCzv&qR#qoEpymlj*y>SVc-j2mIazw1+-p)df4hUP$NOTDrGC_`U'
    '@*{S;kPo$mYI|(~S&4qoz#`f=j&tt6S)?F}_Q2*f8{FwGW~t^2s|$Zs{n#W9Kn%UKqwWEQYYXbYwNC5)i>r+$Q?(8pG4`Uj?FaY_'
    'M<pdJwG2D|$62xPZ)wO1<IsCjEG1hgFP)eUl8OugECX5v-}Z&tDezsZxdYdMX2)dj+h-@s)KC3kz`no37D!dqQVnlVx*lL0Z69=`'
    'Q^9)B^CF!xHU#Z-^-?KocYB3VS2teibEm1)<On$va6tYtjDJ*4iIyKI{Hpf8l(@@>^voRq6avLc_-=z*DeVXKZ}M!;vBwqBn<<oK'
    '(&jtA=zw~?uTRQ#yCV|#>Wpbaih=2nLKSd_wc*iIN&KjA7tD*FWugp;%Df$h`+-1Dw9&)?5wYm0)sf$&L9{spZpuf>eWH?i?;!W5'
    'ZIg9hBqj4sq{O$EO`ZPs=v_CF%bXq_O`@pP^3^HH$XI@lwWzM-j&l~Jv#@^n12jA?AYRkQ`&JEwO<GLzDG_u;YAI|dmnWs-13X@@'
    '^H8tE4XH+dFNrTc{l%uX@YPKqn0C7XV={^8_vn=!DFlA9`uQF&=&}j{kqZ2wvPu8`q?;*J*^vNqPyxAqq8x9!4rk9v#g<pP7tBam'
    '`3gZC7w<QrFA!F!@OE8rErpc_u!w}kjwC65;)!!ZCi;he^EjFEHV@X|va8KqjG7Kea7h+PVsThbFR=qnwHR>-;Ce0>Pr;UUzuob#'
    'h?#w0y^1_G>{u7AL(?tl>vSXuffL|9qh2^mT+<n&z;l-LFy1C5LDwu-Vc<BBCRCy*$0MG*?qQ2`(v-ss0yWr=kR0d2F*Hk)tj_7#'
    '(T4zEwv?z{Wh!s9E2Z;t)h;5?R%Y*;D?@>vgaT9DlX5q}NSxI8bp4(uN-;8}Cq*7l(rRaMPx@$b6FFhHyl}N`zk>in$}4am@dKWR'
    'RS%GSe7k2vloqm{F!|j`nA92H-96&zXQGM62=*Dn8+=7ZyNZgmixGuWe)v6my;t3b9KhXTi|r3|*wkx{9wUWH;EeJw+(;GWfm?U|'
    'i+$FsaL#!_GoKbDQ;r_*)yp%VQQQ50&+&D2{Ly@&GotDcs}rN)fQM>OUQ1hlR#^a2$5`SEKbkc+kF-T*sUsA%HD?02joAC*I-ct7'
    '>_e+yNK)}GIg4V7Y@c-Vc^h#ji)oB3HEBpg8MF;<Z}LzW$Zk1Idaf6ery{OITuyFOA@9qRAg*#1xCNl3VH|3)5GX2vjz&W9Sb?E_'
    'WTeWZ7OZhXjl?UI;3lBiqA0!l$0K&Ks+%(a(7+>#T0&_1dlOr3fb)u2E?W`zpS0%Z_-NnSNzRLG+sFuhy8>q$Fc!NqRAK(WsEi&#'
    'IlH>OmW*hc?(-A69U%<_1ANb=IS%tVr?mh}93TVW#Y-VZS7}Cp!1nf|-iRi?b>Fk!Xi|B@3K&l6`fVc0-BUH;<AG)&SjVA&ZgM5Q'
    'iA(R4?P7~_>Hl2aHV|(~`lCRS(Sv%0Y6s36a$;{IW56yh*Y(=}bc_Zgr9&hH2J5&;+jnK93v^_OqP|TEBwZLOdlhhdrv^Ah*BeuX'
    'PIOApsxNyiXqGLbyF4K6-H?Y4xsqb2d+|*~GK5-VS<Epvuf${jxZ2mCj1SBdw}kDenaUiWq6lgquy*{Au7bK_TJ6Z!R%*uz6gqVO'
    'jP9+*Yicyz(yb!Op-RJIO~h871*=)NabXS;;*=+)vL}|)i2-D@SMZz9R&=yEw{;>mOG1Ou%=H*D&&txU`k{AdrLR|{@$BL97?PoW'
    'iwcdVL(e<?yJ{ohUJ78lR)6B)bEvG5R_-$0`P(X&mKhvMe{*@J6i^jD<{|5L+c;omq>4RAajs{Z(-C<5C>`tTw<Y)|H<(ekPp%9n'
    '%M>KOt8a_>iC~mWUUmh=@|o_D`r?8NLC@FnHctt=u<X*fPe4vx(!ginLGesS)u4<y@n#H&BY9>K4>@)gib_C)_SXFJ<uy*v@-!ik'
    'M<@hs_v+9JaUA)>l7PJNRa$ti%_1FJd@1@f>|uR^pRV;qRk*EUYnB=gQB}%ie7M<KEpi%#z(zqBU~0J#ln3ue8qunA!b+65zIxaO'
    'QK14H<abD$c`CW70PO+0V`tMSWimu<-3oqf8t8Sy<(W#!Cep;6cul6p8C=ERD|>{0HZPMo`<pGoy9@!vyved6rO9R<YNswK)R~Uc'
    '!#@H#GD2x!i4->+O1uS9fXR^t%f~t%o!B=*&+`1#tC_M?VJ7-_A`P42gc9@bB?_N??><)?tbb|=R6>b2-4*IGD#E3y<Xp~MSzQCC'
    'Mw5f?1=$w~hbuK@tLqL7fJ9%m32Q97SpPA`7%yXTIsJ(<CI%xmsQP%Zfb%jdzNRtpP>f*|-!I@jv9zW=_S&zbzTlIvt0mgcJcdPx'
    '>lkXABenPQS2mt<IO948;(Pz^D`%!xH!16(TjWZgu2o4~3yQ<YU)wvC`OPKIYW&QJD@Jt1{P2VAYLemq{$gu8FdT)w<u_}S&3jU_'
    'tP_XLr@6{~OVGr}9=ncNe~LC-;}`>2w9@X@5CC+aN?HWTUQ1)2y~4jsYih%{SO3JrVKYe`W3_Fm_PD0O7#KO2c`UsT6OibdZL_I~'
    '5v$9?mhg;RBAOd3m(K)dGna$3j7RToX!BeyA0e0+(($07SpT7mch^ou{~$Mcy9dzF(nue4=A!0<IU<pEH3IcbI<SOUH&Z9xSwKSB'
    'p&B}?HPTy+b*NDS82UgBrYx3okq2*zwpd=iy8*(ITOO*ZS*UZ4^DkV*Y6j>xQzm8Md(vXR{swh)vFyQ{sOE^_HVHoJ&364_6(Xr%'
    '%$Y)vboz0K%jQ+@mg0&#V53$I>D!rIYJK;hD$_+n-4PfdROw-a>#^mWxRDvzC5DX;vyP3EU(+j{ON^vPBpap^1({u<*<<;8_)M6X'
    '^3w{ZaZ7%weYP1-!#-6O{JiCX=6JZ0#+0_xaEtG47SeKMFD<y3{T4Z_pS8+fh2&53$dCHK=vaSV0J<V}XqqE$qgh8bP27CV0@~XA'
    'I%U$4tU~h?5Q+NP&EuUAJhijfvx>_F`*HiLSC-g{0@2w4>9eq(%n@gWKnD7z@YX?jA<CWuS?UEElvfI@*Al&v2I5Vv5Zl~2yw}C-'
    '3r7j!rV!4Z0hv6@b3YJpmX{uQWs;4qQz2iym!^{;c~EBpX0inzGMfJ1RAxn45L=|#PzQ2}MquK(d*iK}*7)`1@4CirJs0VCUN6Cl'
    ')#YIc{$H3{?Iy;&PnJ1C!Mi2fX`J!_9R{<2kCCR3g4ubPa-zEwa{e<&;XeU_#gY<)&2J7FUJ^s|@T@U2V#8)8Yh%_%BmWA#P)^SF'
    'Aj9LFafmb};N5E?O5&0YKo`c~_)x~9RFHVz729=K$7IA(e5o8Ob81Mh+8?|+5dU`uS3ihji{-^VXZons;z@u7Zlw3zH(4>OFe?X$'
    'Iu~`CekXXnewwLeLS8|_9YkvAo$h+uKw`p;TM<Fb^vg)rBEZ*Dms?tXmi7FWi<7ib#CFc{EPb)OPvT?x3-!9*M)#huDvY3lztVE{'
    '<s2FAUIba)d|n+ZlF79oW}FlG9bK6mXE5Y^q*{XIrZaw{0K0CvU1EY>4(eREBp}VJRkpIoJ=PGd0yjz;6UTaz`5~#UfmohqPN(uu'
    '<=m*5%p9QF71(ZtNb+6hovuOZ&ORck#=S`rZXJTg8jjn)8k^>m&f)tNF3K8R0CV;?bb@QTDo74E`HEvL<<xJGDzzr&jdlqjyvps;'
    'IGF|k^JX;X?P<x6hoHcM<-?cf-VxKll4QaF!yDg1l0yv*OYzV&m>>PRc*Cy3Eqmf|fjyn&O=1am-r8kZl@|ZxkznpG-kYk#dGGc_'
    'h5l%)PdZjU@#p73E<TImEPspDcHc%xJhN_EwQz&*_eMCnx}6MF`kX&pod5WxCNk*|zgC$jV4~m^Mexd?C@#9=oLBzrZh7>m_;t$4'
    '3Y^*KAiy|~V&X;m<OLvsbX6nR-Tq>b(&1U=(Mm%V@&{g3;?-#Bo2Nx2q!AC$B*eRNEjAOKNr=i+l=~ZDup9-gZp>?Fdd^eNcRef8'
    'yb~N?k-c9S2p?Pwj4EhD`w@1O7^E_D8l5R!N&u?b*JAfj0>1ujnnfJ=5N!Y^lvX1oV&Y<Xb^gpb(^P;>izNG;GRO9jw=>Kyj=-)t'
    'SVqqJ7parmYX%>>B5MnZTI7Bj#&*&;tV!SyQd%1?!D$HS<PeTQ$LxE$s|rF`T|5A*A6Fc_vGL#t1(Qt}^uEQp_<M$Y01pLeUf90G'
    '_=j>cjQ?wp%+6ona$LuEgvQ9a)rX9!m{8_UuN@&3#tcN9iopcvq`z+;mOo@h)iK<GH%5H^G=(T;wQ`1&7lJvc$Z<i^wvf4S2*fel'
    'ho%IEQtNi{&GU`E#_O`Wr9v?hZ&ebvvIiiBYpSAK0rv5q!PhEFB@{<MA_*j**_O`Rd3ajprJuA1T@gK(FJd88M=myw5>=ZiPJ}Rt'
    'N!zmG>&QKzk(VJtbW-fRzdT7(n>0v4!(K{U{{ZV;@>|+*##hLD_&Sl_4NuzV#vuZ+8pJ>1#fNQ@bhxmx+W-In<%>+c1Cy&|00F+?'
    '5VzT%1^@s6a@9=T6c;-%0{{R300dcD'
)


def load_module(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location("mechanical_validator_under_test", path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot import validator {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def materialize_branch_coverage_fixture(destination: Path) -> None:
    packed = lzma.decompress(base64.b85decode(BRANCH_COVERAGE_FIXTURE_B85))
    if packed[:7] != b"MOBSFX1":
        raise AssertionError("branch-coverage fixture magic mismatch")
    offset = 7
    file_count = struct.unpack_from("<H", packed, offset)[0]
    offset += 2
    destination.mkdir(parents=True)
    names: list[str] = []
    for _index in range(file_count):
        name_size, data_size = struct.unpack_from("<HQ", packed, offset)
        offset += struct.calcsize("<HQ")
        name = packed[offset:offset + name_size].decode("ascii")
        offset += name_size
        data = packed[offset:offset + data_size]
        offset += data_size
        if Path(name).name != name or name in names:
            raise AssertionError("unsafe/duplicate branch-coverage fixture member")
        names.append(name)
        (destination / name).write_bytes(data)
    if offset != len(packed):
        raise AssertionError("branch-coverage fixture trailing bytes")


def materialize_registered_smoke_fixture(module: ModuleType, destination: Path) -> None:
    """Extract the byte-authentic fixture, then retain the exact frozen smoke set."""

    materialize_branch_coverage_fixture(destination)
    configuration_ids = set(module.SMOKE_CONFIGURATION_IDS)

    def retain(table: str, predicate: Callable[[Mapping[str, str]], bool]) -> list[dict[str, str]]:
        fields, rows = read_csv(destination / table)
        kept = [row for row in rows if predicate(row)]
        write_csv(destination / table, fields, kept)
        return kept

    retain("configurations.csv", lambda row: row["configuration_id"] in configuration_ids)
    for table in ("packets.csv", "neighbor_pairs.csv", "relations.csv", "checkpoints.csv"):
        retain(table, lambda row: row["configuration_id"] in configuration_ids)
    statuses = retain(
        "operator_status.csv", lambda row: row["configuration_id"] in configuration_ids
    )
    operator_ids = {row["operator_id"] for row in statuses}
    if operator_ids != set(module.SMOKE_OPERATOR_IDS):
        raise AssertionError("embedded fixture does not contain the frozen smoke operator set")
    for table in (
        "operator_entries.csv", "moment_diagnostics.csv", "affine_objectivity.csv",
        "rigid_basis.csv", "rank_status.csv", "nullspace_modes.csv",
        "nullspace_metrics.csv", "grid_gauge.csv",
    ):
        retain(table, lambda row: row["operator_id"] in operator_ids)
    retain(
        "grid_nodes.csv",
        lambda row: row["sampling_operator_id"] in operator_ids
        and row["derivative_operator_id"] in operator_ids,
    )
    retain("exact_reference.csv", lambda row: row["configuration_id"] in configuration_ids)
    retain(
        "invariance.csv",
        lambda row: row["base_operator_id"] in operator_ids
        and row["transformed_operator_id"] in operator_ids,
    )
    controls = retain(
        "permutation_controls.csv", lambda row: row["operator_id"] in operator_ids
    )
    control_ids = {row["control_id"] for row in controls}
    retain("permutation_entries.csv", lambda row: row["control_id"] in control_ids)

    # The embedded fixture predates the preregistered end-to-end finite
    # operation counts.  Upgrade only those reporting cells from the retained
    # authoritative packet/relation state; measured and target values stay
    # byte-identical.
    packet_rows = read_csv(destination / "packets.csv")[1]
    packet_positions: dict[str, dict[int, tuple[Decimal, Decimal, Decimal]]] = {}
    for row in packet_rows:
        packet_positions.setdefault(row["configuration_id"], {})[int(row["packet_id"])] = (
            Decimal.from_float(float.fromhex(row["x_m"])),
            Decimal.from_float(float.fromhex(row["y_m"])),
            Decimal.from_float(float.fromhex(row["z_m"])),
        )
    relation_rows = read_csv(destination / "relations.csv")[1]
    relation_lookup = {
        (row["configuration_id"], row["relation_id"]): row for row in relation_rows
    }
    status_lookup = {row["operator_id"]: row for row in statuses}
    transforms = {
        "proper_quaternion_rotation": (module.ROTATION_Q, (module.Q(0),) * 3, module.Q(1)),
        "signed_axis_rotation": (
            ((module.Q(1), module.Q(0), module.Q(0)),
             (module.Q(0), module.Q(-1), module.Q(0)),
             (module.Q(0), module.Q(0), module.Q(-1))),
            (module.Q(0),) * 3, module.Q(1),
        ),
        "translation": (
            ((module.Q(1), module.Q(0), module.Q(0)),
             (module.Q(0), module.Q(1), module.Q(0)),
             (module.Q(0), module.Q(0), module.Q(1))),
            module.TRANSLATION_Q, module.Q(1),
        ),
        "scale_half": (
            ((module.Q(1), module.Q(0), module.Q(0)),
             (module.Q(0), module.Q(1), module.Q(0)),
             (module.Q(0), module.Q(0), module.Q(1))),
            (module.Q(0),) * 3, module.Q(1, 2),
        ),
        "scale_double": (
            ((module.Q(1), module.Q(0), module.Q(0)),
             (module.Q(0), module.Q(1), module.Q(0)),
             (module.Q(0), module.Q(0), module.Q(1))),
            (module.Q(0),) * 3, module.Q(2),
        ),
    }
    affine_fields, affine_rows = read_csv(destination / "affine_objectivity.csv")
    for row in affine_rows:
        if row["test_kind"] not in {"finite_bond_length", "finite_oriented_volume"}:
            continue
        config_id = status_lookup[row["operator_id"]]["configuration_id"]
        relation = relation_lookup[(config_id, row["relation_id"])]
        rotation_q, translation_q, scale_q = transforms[row["field"]]
        rotation = [[Decimal(value.numerator) / Decimal(value.denominator) for value in axis]
                    for axis in rotation_q]
        translation = [Decimal(value.numerator) / Decimal(value.denominator)
                       for value in translation_q]
        scale = Decimal(scale_q.numerator) / Decimal(scale_q.denominator)
        measured = Decimal.from_float(float.fromhex(row["measured_value"]))
        target = Decimal.from_float(float.fromhex(row["target_value"]))
        absolute = Decimal.from_float(float.fromhex(row["absolute_error"]))
        operand_scale = module.finite_operand_scale(
            relation, packet_positions[config_id], rotation, translation, scale,
            measured, target,
        )
        operations = 72 if row["test_kind"] == "finite_bond_length" else 134
        bound = (
            Decimal(256) * module.gamma_n(operations) * operand_scale
            + Decimal(256) * module.MIN_NORMAL
        )
        row["operation_count"] = str(operations)
        row["normalization_scale"] = _decimal_hex(operand_scale)
        row["normalized_error"] = _decimal_hex(absolute / operand_scale)
        row["roundoff_bound"] = _decimal_hex(bound)
        row["pass"] = str(absolute <= bound).lower()
    write_csv(destination / "affine_objectivity.csv", affine_fields, affine_rows)

    summary = json.loads((destination / "summary.json").read_text(encoding="utf-8"))
    summary["schema"] = module.SUMMARY_SCHEMA
    summary["provisional"] = True
    summary["sweep_complete"] = False
    summary["registered_configuration_ids"] = sorted(configuration_ids)
    summary["registered_operator_ids"] = sorted(operator_ids)
    summary["row_counts"] = {
        name: len(read_csv(destination / name)[1]) for name in sorted(module.CSV_SCHEMAS)
    }
    summary = {key: summary[key] for key in module.SUMMARY_KEY_ORDER}
    write_json(destination / "summary.json", summary)
    refresh_manifest(module, destination)


def write_json(path: Path, value: Any) -> None:
    path.write_bytes(
        (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode(
            "utf-8"
        )
    )


def write_csv(path: Path, fields: Sequence[str], rows: Sequence[Mapping[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        return list(reader.fieldnames or ()), list(reader)


def hx(value: float) -> str:
    value = float(value)
    if value == 0.0:
        value = 0.0
    return value.hex()


def grouped_digest(prefix: bytes, fields: Sequence[str], rows: Sequence[Mapping[str, str]]) -> str:
    digest = hashlib.sha256(prefix + b"\n")
    for row in rows:
        for field in fields:
            digest.update(b"\0")
            digest.update(row[field].encode())
        digest.update(b"\n")
    return digest.hexdigest()


def manifest_payload(schema: str, hashes: Mapping[str, str]) -> bytes:
    names = sorted(hashes)
    lines = ["{", '  "algorithm": "SHA-256",', '  "files": {']
    for index, name in enumerate(names):
        comma = "," if index + 1 < len(names) else ""
        lines.append(f"    {json.dumps(name)}: {json.dumps(hashes[name])}{comma}")
    lines.extend(("  },", f'  "schema": {json.dumps(schema)}', "}"))
    return "\n".join(lines).encode()


def refresh_manifest(module: ModuleType, bundle: Path) -> None:
    hashes = {
        name: hashlib.sha256((bundle / name).read_bytes()).hexdigest()
        for name in sorted(module.REQUIRED_FILES)
    }
    write_json(
        bundle / "manifest.json",
        {
            "algorithm": "SHA-256",
            "files": hashes,
            "pre_hash_sha256": hashlib.sha256(
                manifest_payload(module.MANIFEST_SCHEMA, hashes)
            ).hexdigest(),
            "schema": module.MANIFEST_SCHEMA,
        },
    )


def materialize_authentic_a_pair_failure_fixture(
    module: ModuleType, bundle: Path, failed_half: str
) -> None:
    """Apply the producer's closed A-pair fixture transform.

    The six state-machine tables are cryptographically bound before and after
    the transform to the authentic summary-v2 GCC producer bundles.  This is
    not an arbitrary mutation accepted on its own authority: any byte drift
    from either the positive producer state or the two producer failure states
    fails before the semantic validator runs.
    """

    if failed_half not in {"sampling", "derivative"}:
        raise AssertionError(f"unknown Candidate-A fixture half {failed_half!r}")
    for name, expected in AUTHENTIC_A_PAIR_STATE_HASHES["positive"].items():
        actual = hashlib.sha256((bundle / name).read_bytes()).hexdigest()
        if actual != expected:
            raise AssertionError(f"positive producer state hash drift for {name}")

    sampling_id = "base.filament.r205.original.A.p000.S"
    derivative_id = "base.filament.r205.original.A.p000.D"
    target = sampling_id if failed_half == "sampling" else derivative_id

    entry_fields, entries = read_csv(bundle / "operator_entries.csv")
    entries = [row for row in entries if row["operator_id"] != target]
    write_csv(bundle / "operator_entries.csv", entry_fields, entries)

    status_fields, statuses = read_csv(bundle / "operator_status.csv")
    for status in statuses:
        if status["operator_id"] == sampling_id:
            status["rank_applicable"] = "false"
        if status["operator_id"] != target:
            continue
        status.update({
            "build_status": "numerical_failure",
            "operator_payload_sha256": (
                "734cb63e46d08e894d4ed350e7d74564dce2d7d58a978e8f2442cf2a8b740db0"
            ),
            "row_normalization_complete": "false",
            "first_invalid_row": "0",
            "rank_applicable": "false",
            "failure_stage": "row_normalization",
            "failure_reason": "zero_row_norm",
            "failure_witness_row": "0",
            "failure_witness_value": "0x0.0p+0",
            "failure_witness_ieee754_bits": "0000000000000000",
            "failure_witness_class": "finite_zero",
        })
    write_csv(bundle / "operator_status.csv", status_fields, statuses)

    for table in (
        "rank_status.csv", "nullspace_modes.csv", "nullspace_metrics.csv",
        "grid_gauge.csv",
    ):
        fields, rows = read_csv(bundle / table)
        rows = [row for row in rows if row["operator_id"] != sampling_id]
        write_csv(bundle / table, fields, rows)

    for name, expected in AUTHENTIC_A_PAIR_STATE_HASHES[failed_half].items():
        actual = hashlib.sha256((bundle / name).read_bytes()).hexdigest()
        if actual != expected:
            raise AssertionError(
                f"{failed_half} failure producer state hash drift for {name}"
            )

    summary = json.loads((bundle / "summary.json").read_text(encoding="utf-8"))
    summary.update({
        "mode": "failure_fixture",
        "provisional": True,
        "sweep_complete": False,
        "negative_control_reproduced": False,
        "decisive_rank_rows_all_unambiguous": False,
        "candidate_findings": {
            "A": "negative_control_failed", "B": "inconclusive",
            "C": "inconclusive", "D": "inconclusive",
        },
        "decision": "stop_inconclusive_or_implementation_failure",
    })
    summary["row_counts"] = {
        name: len(read_csv(bundle / name)[1]) for name in sorted(module.CSV_SCHEMAS)
    }
    summary = {key: summary[key] for key in module.SUMMARY_KEY_ORDER}
    write_json(bundle / "summary.json", summary)
    refresh_manifest(module, bundle)


def refresh_summary_row_counts(module: ModuleType, bundle: Path) -> None:
    summary = json.loads((bundle / "summary.json").read_text(encoding="utf-8"))
    summary["row_counts"] = {
        name: len(read_csv(bundle / name)[1]) for name in sorted(module.CSV_SCHEMAS)
    }
    summary = {key: summary[key] for key in module.SUMMARY_KEY_ORDER}
    write_json(bundle / "summary.json", summary)


def refresh_group_digest(module: ModuleType, bundle: Path, table: str, configuration_id: str) -> None:
    fields, rows = read_csv(bundle / table)
    selected = [row for row in rows if row["configuration_id"] == configuration_id]
    prefix = {
        "packets.csv": b"MLS-MECHANICAL-OBSERVABILITY-PACKETS-v1",
        "neighbor_pairs.csv": b"MLS-MECHANICAL-OBSERVABILITY-NEIGHBORS-v1",
        "relations.csv": b"MLS-MECHANICAL-OBSERVABILITY-RELATIONS-v1",
    }[table]
    digest = grouped_digest(prefix, fields, selected)
    config_fields, configurations = read_csv(bundle / "configurations.csv")
    field = {
        "packets.csv": "packet_payload_sha256",
        "neighbor_pairs.csv": "neighbor_payload_sha256",
        "relations.csv": "relation_payload_sha256",
    }[table]
    for row in configurations:
        if row["configuration_id"] == configuration_id:
            row[field] = digest
    write_csv(bundle / "configurations.csv", config_fields, configurations)


def refresh_operator_digest(module: ModuleType, bundle: Path, operator_id: str) -> None:
    entry_fields, entries = read_csv(bundle / "operator_entries.csv")
    selected = [row for row in entries if row["operator_id"] == operator_id]
    digest = grouped_digest(b"MLS-MECHANICAL-OBSERVABILITY-OPERATOR-v1", entry_fields, selected)
    status_fields, statuses = read_csv(bundle / "operator_status.csv")
    for row in statuses:
        if row["operator_id"] == operator_id:
            row["operator_payload_sha256"] = digest
    write_csv(bundle / "operator_status.csv", status_fields, statuses)


def refresh_permutation_digest(module: ModuleType, bundle: Path, control_id: str) -> None:
    entry_fields, entries = read_csv(bundle / "permutation_entries.csv")
    selected = [row for row in entries if row["control_id"] == control_id]
    digest = grouped_digest(
        b"MLS-MECHANICAL-OBSERVABILITY-PERMUTATION-OPERATOR-v2",
        entry_fields,
        selected,
    )
    control_fields, controls = read_csv(bundle / "permutation_controls.csv")
    for row in controls:
        if row["control_id"] == control_id:
            row["raw_payload_sha256"] = digest
    write_csv(bundle / "permutation_controls.csv", control_fields, controls)


def _decimal_hex(value: Decimal) -> str:
    return hx(float(value))


def _operator_rows(
    module: ModuleType,
    operator_id: str,
    candidate: str,
    matrix: Sequence[Sequence[Decimal]],
    packet_ids: Sequence[int],
    relation_ids: Sequence[str],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row_index, matrix_row in enumerate(matrix):
        for column_index, value in enumerate(matrix_row):
            emitted = float(value)
            if emitted == 0.0:
                continue
            if candidate == "B":
                owner = str(packet_ids[row_index // 6])
                row_kind = "symmetric_gradient"
                component = module.A_ROW_COMPONENTS[row_index % 6]
                units = "per_m"
            else:
                owner = relation_ids[row_index]
                row_kind = "bond_length_rate"
                component = "length"
                units = "one"
            rows.append(dict(zip(module.OPERATOR_ENTRY_FIELDS, (
                operator_id, str(row_index), str(column_index), "packet",
                str(packet_ids[column_index // 3]), module.AXES[column_index % 3],
                row_kind, owner, component, hx(emitted), units,
            ), strict=True)))
    return rows


def _normalized_product(
    module: ModuleType,
    matrix: Sequence[Sequence[Decimal]],
    columns: Sequence[Sequence[Decimal]],
) -> Decimal:
    if not columns:
        return Decimal(0)
    images = [module.decimal_matvec(matrix, column) for column in columns]
    numerator = module.decimal_norm(value for image in images for value in image)
    denominator = module.decimal_matrix_norm(matrix) * module.decimal_norm(
        value for column in columns for value in column
    )
    return numerator / max(denominator, module.MIN_NORMAL)


def rewrite_c_rank_contract_negative(
    module: ModuleType, bundle: Path, *, orthogonality: bool
) -> None:
    """Create a structurally valid C residual/quotient negative result."""

    operator_id = "exact.planar_square_plus_diagonal_and_volume.C"
    _status_fields, statuses = read_csv(bundle / "operator_status.csv")
    status = next(row for row in statuses if row["operator_id"] == operator_id)
    _entry_fields, entries = read_csv(bundle / "operator_entries.csv")
    matrix = module.dense_operator(
        status, [row for row in entries if row["operator_id"] == operator_id]
    )
    normalized = module.normalized_rows(matrix)
    rank_fields, rank_rows = read_csv(bundle / "rank_status.csv")
    rank_summary = next(
        row for row in rank_rows
        if row["operator_id"] == operator_id and row["record_kind"] == "summary"
    )
    tolerance = Decimal.from_float(float.fromhex(rank_summary["residual_tolerance"]))
    _rigid_fields, rigid_rows = read_csv(bundle / "rigid_basis.csv")
    rigid_q = module.basis_columns(
        rigid_rows, operator_id, "orthonormal", int(status["column_count"])
    )
    null_fields, null_rows = read_csv(bundle / "nullspace_modes.csv")
    complete = module.basis_columns(
        null_rows, operator_id, "complete_kernel", int(status["column_count"])
    )
    nonrigid = module.basis_columns(
        null_rows, operator_id, "nonrigid", int(status["column_count"])
    )
    if len(nonrigid) != 1:
        raise AssertionError("registered planar C control lost its one-dimensional quotient")
    z = nonrigid[0]
    delta = Decimal(256) * tolerance
    if orthogonality:
        perturbation = rigid_q[0]
    else:
        perturbation = list(normalized[0])
        for mode in complete:
            projection = module.decimal_dot(perturbation, mode)
            perturbation = [
                value - projection * basis_value
                for value, basis_value in zip(perturbation, mode, strict=True)
            ]
        perturbation_norm = module.decimal_norm(perturbation)
        if perturbation_norm == 0:
            raise AssertionError("could not resolve a C row-space perturbation")
        perturbation = [value / perturbation_norm for value in perturbation]
    z_changed = [
        value + delta * perturb
        for value, perturb in zip(z, perturbation, strict=True)
    ]
    z_norm = module.decimal_norm(z_changed)
    z_changed = [value / z_norm for value in z_changed]
    complete_changed = module.orthonormalize_columns(
        [*rigid_q, z_changed], Decimal("1e-50")
    )
    if len(complete_changed) != 7:
        raise AssertionError("mutated C complete basis construction failed")

    def rounded_columns(columns: Sequence[Sequence[Decimal]]) -> list[list[Decimal]]:
        return [
            [Decimal.from_float(float(value)) for value in column]
            for column in columns
        ]

    complete_changed = rounded_columns(complete_changed)
    nonrigid_changed = rounded_columns([z_changed])
    packet_rows = read_csv(bundle / "packets.csv")[1]
    packet_ids = [
        int(row["packet_id"]) for row in packet_rows
        if row["configuration_id"] == status["configuration_id"]
    ]
    replacement_modes: list[dict[str, str]] = []
    for basis_kind, columns in (
        ("complete_kernel", complete_changed), ("nonrigid", nonrigid_changed)
    ):
        for mode_index, column in enumerate(columns):
            for dof_index, value in enumerate(column):
                replacement_modes.append(dict(zip(module.NULLSPACE_MODE_FIELDS, (
                    operator_id, basis_kind, str(mode_index), str(dof_index), "packet",
                    str(packet_ids[dof_index // 3]), module.AXES[dof_index % 3],
                    hx(float(value)),
                ), strict=True)))
    null_rows = [row for row in null_rows if row["operator_id"] != operator_id]
    null_rows.extend(replacement_modes)
    null_rows.sort(key=lambda row: (
        row["operator_id"], row["basis_kind"], int(row["mode_index"]),
        int(row["dof_index"]),
    ))
    write_csv(bundle / "nullspace_modes.csv", null_fields, null_rows)

    metric_fields, metric_rows = read_csv(bundle / "nullspace_metrics.csv")
    metric_rows = [row for row in metric_rows if row["operator_id"] != operator_id]
    matrix_norm = module.decimal_matrix_norm(normalized)
    for basis_kind, columns in (
        ("complete_kernel", complete_changed), ("nonrigid", nonrigid_changed)
    ):
        for mode_index, mode in enumerate(columns):
            image = module.decimal_norm(module.decimal_matvec(normalized, mode))
            denominator = max(matrix_norm * module.decimal_norm(mode), module.MIN_NORMAL)
            residual = image / denominator
            projection = module.decimal_norm(
                module.decimal_dot(rigid_mode, mode) for rigid_mode in rigid_q
            )
            orthogonal = projection if basis_kind == "nonrigid" else Decimal(0)
            passed = residual <= tolerance and (
                basis_kind != "nonrigid" or orthogonal <= tolerance
            )
            metric_rows.append(dict(zip(module.NULLSPACE_METRIC_FIELDS, (
                operator_id, basis_kind, str(mode_index), hx(float(image)),
                hx(float(denominator)), hx(float(residual)), hx(float(projection)),
                hx(float(orthogonal)), hx(float(tolerance)),
                str(passed).lower(), "false",
            ), strict=True)))
    metric_rows.sort(key=lambda row: (
        row["operator_id"], row["basis_kind"], int(row["mode_index"])
    ))
    write_csv(bundle / "nullspace_metrics.csv", metric_fields, metric_rows)

    aggregate_rigid = _normalized_product(module, normalized, rigid_q)
    aggregate_null = _normalized_product(module, normalized, complete_changed)
    aggregate_nonrigid = _normalized_product(module, normalized, nonrigid_changed)
    aggregate_orthogonality = module.decimal_norm(
        module.decimal_dot(rigid_mode, nonrigid_mode)
        for rigid_mode in rigid_q for nonrigid_mode in nonrigid_changed
    ) / max(
        module.decimal_norm(value for mode in rigid_q for value in mode)
        * module.decimal_norm(value for mode in nonrigid_changed for value in mode),
        module.MIN_NORMAL,
    )
    for row in rank_rows:
        if row["operator_id"] != operator_id:
            continue
        row["normalized_rigid_residual"] = hx(float(aggregate_rigid))
        row["normalized_null_residual"] = hx(float(aggregate_null))
        row["normalized_nonrigid_residual"] = hx(float(aggregate_nonrigid))
        row["rigid_orthogonality_residual"] = hx(float(aggregate_orthogonality))
    write_csv(bundle / "rank_status.csv", rank_fields, rank_rows)

    summary = json.loads((bundle / "summary.json").read_text(encoding="utf-8"))
    summary["decisive_rank_rows_all_unambiguous"] = False
    write_json(bundle / "summary.json", summary)
    refresh_manifest(module, bundle)


def rewrite_a_mode_contract_negative(module: ModuleType, bundle: Path) -> None:
    """Create an A sampling-null mode that is observably outside ker(S)."""

    operator_id = "base.filament.r205.original.A.p000.S"
    _status_fields, statuses = read_csv(bundle / "operator_status.csv")
    status = next(row for row in statuses if row["operator_id"] == operator_id)
    _entry_fields, entries = read_csv(bundle / "operator_entries.csv")
    matrix = module.dense_operator(
        status, [row for row in entries if row["operator_id"] == operator_id]
    )
    normalized = module.normalized_rows(matrix)
    rank_fields, rank_rows = read_csv(bundle / "rank_status.csv")
    rank_summary = next(
        row for row in rank_rows
        if row["operator_id"] == operator_id and row["record_kind"] == "summary"
    )
    tolerance = Decimal.from_float(float.fromhex(rank_summary["residual_tolerance"]))
    null_fields, null_rows = read_csv(bundle / "nullspace_modes.csv")
    modes = module.basis_columns(
        null_rows, operator_id, "sampling_null", int(status["column_count"])
    )
    perturbation = list(normalized[0])
    for mode in modes:
        projection = module.decimal_dot(perturbation, mode)
        perturbation = [
            value - projection * basis_value
            for value, basis_value in zip(perturbation, mode, strict=True)
        ]
    perturbation_norm = module.decimal_norm(perturbation)
    if perturbation_norm == 0:
        raise AssertionError("could not resolve an A row-space perturbation")
    perturbation = [value / perturbation_norm for value in perturbation]
    delta = Decimal(256) * tolerance
    changed = [
        value + delta * perturb
        for value, perturb in zip(modes[0], perturbation, strict=True)
    ]
    changed_norm = module.decimal_norm(changed)
    modes[0] = [Decimal.from_float(float(value / changed_norm)) for value in changed]
    modes = [
        [Decimal.from_float(float(value)) for value in mode] for mode in modes
    ]

    node_count = int(status["column_count"]) // 3
    replacement_modes: list[dict[str, str]] = []
    for mode_index, mode in enumerate(modes):
        for dof_index, value in enumerate(mode):
            replacement_modes.append(dict(zip(module.NULLSPACE_MODE_FIELDS, (
                operator_id, "sampling_null", str(mode_index), str(dof_index),
                "grid_node", str(dof_index // 3 + 1), module.AXES[dof_index % 3],
                hx(float(value)),
            ), strict=True)))
    null_rows = [row for row in null_rows if row["operator_id"] != operator_id]
    null_rows.extend(replacement_modes)
    null_rows.sort(key=lambda row: (
        row["operator_id"], row["basis_kind"], int(row["mode_index"]),
        int(row["dof_index"]),
    ))
    write_csv(bundle / "nullspace_modes.csv", null_fields, null_rows)

    metric_fields, metric_rows = read_csv(bundle / "nullspace_metrics.csv")
    metric_rows = [row for row in metric_rows if row["operator_id"] != operator_id]
    raw_norm = module.decimal_matrix_norm(matrix)
    for mode_index, mode in enumerate(modes):
        image = module.decimal_norm(module.decimal_matvec(matrix, mode))
        denominator = max(raw_norm * module.decimal_norm(mode), module.MIN_NORMAL)
        residual = image / denominator
        metric_rows.append(dict(zip(module.NULLSPACE_METRIC_FIELDS, (
            operator_id, "sampling_null", str(mode_index), hx(float(image)),
            hx(float(denominator)), hx(float(residual)), hx(0), hx(0),
            hx(float(tolerance)), str(residual <= tolerance).lower(), "false",
        ), strict=True)))
    metric_rows.sort(key=lambda row: (
        row["operator_id"], row["basis_kind"], int(row["mode_index"])
    ))
    write_csv(bundle / "nullspace_metrics.csv", metric_fields, metric_rows)

    aggregate = _normalized_product(module, normalized, modes)
    for row in rank_rows:
        if row["operator_id"] != operator_id:
            continue
        row["normalized_rigid_residual"] = hx(0)
        row["normalized_null_residual"] = hx(float(aggregate))
        row["normalized_nonrigid_residual"] = hx(float(aggregate))
        row["rigid_orthogonality_residual"] = hx(0)
    write_csv(bundle / "rank_status.csv", rank_fields, rank_rows)

    tables = {
        name: read_csv(bundle / name)[1] for name in (
            "configurations.csv", "packets.csv", "relations.csv", "operator_status.csv",
            "operator_entries.csv", "moment_diagnostics.csv", "grid_nodes.csv",
        )
    }
    configurations = module.validate_configuration_rows(tables["configurations.csv"])
    packet_groups, positions, positions_q = module.validate_packet_tables(
        tables["configurations.csv"], tables["packets.csv"]
    )
    topology = module.validate_relations(
        tables["configurations.csv"], tables["relations.csv"], positions, positions_q
    )
    generic = {
        config_id for config_id, facts in topology.items() if facts["generic_solid_gate"]
    }
    status_by_id, matrices, _moments, _reference = module.validate_operator_tables(
        tables["configurations.csv"], generic, packet_groups, positions,
        tables["relations.csv"], tables["operator_status.csv"],
        tables["operator_entries.csv"], tables["moment_diagnostics.csv"],
        tables["grid_nodes.csv"],
    )
    controls = module.validate_candidate_a_inputs(
        tables["grid_nodes.csv"], configurations, positions, status_by_id,
        tables["operator_entries.csv"], matrices,
    )
    control = controls[operator_id]
    sampling = control["sampling"]
    derivative = control["derivative"]
    sampling_norm = module.decimal_matrix_norm(sampling)
    gauge_fields, gauge_rows = read_csv(bundle / "grid_gauge.csv")
    rows_by_mode = {
        int(row["mode_index"]): row for row in gauge_rows
        if row["operator_id"] == operator_id
    }
    for mode_index, mode in enumerate(modes):
        row = rows_by_mode[mode_index]
        axis = mode_index % 3
        scalar_mode = [mode[3 * node + axis] for node in range(node_count)]
        sampling_image = module.decimal_matvec(sampling, mode)
        sampling_denominator = max(
            sampling_norm * module.decimal_norm(mode), module.MIN_NORMAL
        )
        sampling_residual = module.decimal_norm(sampling_image) / sampling_denominator
        derivative_image = module.decimal_matvec(derivative, mode)
        derivative_max = max((abs(value) for value in derivative_image), default=Decimal(0))
        derivative_rms = module.decimal_norm(derivative_image) / Decimal(
            len(derivative_image)
        ).sqrt()
        roundoff = module.MIN_NORMAL
        for stencil in control["gradient_stencils"]:
            absolute_sum = module.dsum(
                abs(scalar_mode[node]) * module.decimal_norm(gradient)
                for node, gradient in stencil.items()
            )
            operations = 3 * len(stencil)
            gamma = Decimal(operations) * module.EPS64 / (
                Decimal(1) - Decimal(operations) * module.EPS64
            )
            roundoff = max(roundoff, Decimal(128) * gamma * absolute_sum)
        visible = derivative_max > max(Decimal("1e-10"), Decimal("1e4") * roundoff)
        accepted = sampling_residual <= tolerance
        row["sampling_residual_normalized"] = hx(float(sampling_residual))
        row["derivative_max_per_s"] = hx(float(derivative_max))
        row["derivative_rms_per_s"] = hx(float(derivative_rms))
        row["derivative_roundoff_bound_per_s"] = hx(float(roundoff))
        row["visibility_ratio"] = hx(float(derivative_max / roundoff))
        row["gradient_visible"] = str(visible).lower()
        row["accepted"] = str(accepted).lower()
        row["pass"] = str(accepted and visible).lower()
    write_csv(bundle / "grid_gauge.csv", gauge_fields, gauge_rows)

    summary = json.loads((bundle / "summary.json").read_text(encoding="utf-8"))
    summary["negative_control_reproduced"] = False
    summary["decisive_rank_rows_all_unambiguous"] = False
    summary["candidate_findings"] = {
        "A": "negative_control_failed", "B": "inconclusive",
        "C": "inconclusive", "D": "inconclusive",
    }
    summary["decision"] = "stop_inconclusive_or_implementation_failure"
    write_json(bundle / "summary.json", summary)
    refresh_manifest(module, bundle)


def _make_bundle_legacy(module: ModuleType, bundle: Path) -> None:
    bundle.mkdir(parents=True)
    configuration_id = "tetrahedron_k4"
    packet_values = (
        (1, (0.0, 0.0, 0.0)),
        (2, (1.0, 0.0, 0.0)),
        (3, (0.0, 1.0, 0.0)),
        (4, (0.0, 0.0, 1.0)),
    )
    packets: list[dict[str, str]] = []
    for index, (packet_id, position) in enumerate(packet_values):
        packets.append(
            dict(
                zip(
                    module.PACKET_FIELDS,
                    (
                        configuration_id, str(index), str(packet_id), "1",
                        *(hx(value) for value in position),
                        hx(0), hx(0), hx(0), hx(0), hx(0), hx(0),
                    ),
                    strict=True,
                )
            )
        )
    positions = {packet_id: position for packet_id, position in packet_values}
    neighbors: list[dict[str, str]] = []
    for low, high in itertools.combinations(sorted(positions), 2):
        offset = tuple(positions[high][axis] - positions[low][axis] for axis in range(3))
        distance_squared = sum(value * value for value in offset)
        weight = (1.0 - distance_squared / 4.0) ** 2
        neighbors.append(
            dict(
                zip(
                    module.NEIGHBOR_PAIR_FIELDS,
                    (
                        configuration_id, "p000", str(low), str(high), hx(distance_squared),
                        hx(4), "true", "true", "true", hx(weight),
                    ),
                    strict=True,
                )
            )
        )
    relations: list[dict[str, str]] = []
    edges = list(itertools.combinations(sorted(positions), 2))
    for index, (low, high) in enumerate(edges):
        offset = tuple(positions[high][axis] - positions[low][axis] for axis in range(3))
        length = math.sqrt(sum(value * value for value in offset))
        relations.append(
            dict(
                zip(
                    module.RELATION_FIELDS,
                    (
                        configuration_id, str(index), f"bond_{low}_{high}", "bond", "NA",
                        str(low), str(high), "NA", "retained", "explicit", hx(length), "m", "NA",
                    ),
                    strict=True,
                )
            )
        )
    packet_digest = grouped_digest(
        b"MLS-MECHANICAL-OBSERVABILITY-PACKETS-v1", module.PACKET_FIELDS, packets
    )
    neighbor_digest = grouped_digest(
        b"MLS-MECHANICAL-OBSERVABILITY-NEIGHBORS-v1", module.NEIGHBOR_PAIR_FIELDS, neighbors
    )
    relation_digest = grouped_digest(
        b"MLS-MECHANICAL-OBSERVABILITY-RELATIONS-v1", module.RELATION_FIELDS, relations
    )
    checkpoint = "a" * 64
    configurations = [
        dict(
            zip(
                module.CONFIGURATION_FIELDS,
                (
                    configuration_id, configuration_id, "exact_control", "base", "H2",
                    "identity", "p000", "4", hx(1), hx(2), hx(1), "3", "true", "6",
                    "6", "3", "6", "true", "false", "false", packet_digest,
                    neighbor_digest, relation_digest, checkpoint, checkpoint, "true",
                ),
                strict=True,
            )
        )
    ]

    entries: list[dict[str, str]] = []
    packet_index = {packet_id: index for index, (packet_id, _position) in enumerate(packet_values)}
    for row_index, (low, high) in enumerate(edges):
        offset = tuple(positions[high][axis] - positions[low][axis] for axis in range(3))
        length = math.sqrt(sum(value * value for value in offset))
        for packet_id, sign in ((low, -1.0), (high, 1.0)):
            for axis, component in enumerate(("x", "y", "z")):
                value = sign * offset[axis] / length
                if value == 0.0:
                    continue
                column = 3 * packet_index[packet_id] + axis
                entries.append(
                    dict(
                        zip(
                            module.OPERATOR_ENTRY_FIELDS,
                            (
                                "C_tetrahedron", str(row_index), str(column), "packet", str(packet_id),
                                component, "central_bond", f"bond_{low}_{high}", "length_rate",
                                hx(value), "dimensionless",
                            ),
                            strict=True,
                        )
                    )
                )
    entries.sort(key=lambda row: (row["operator_id"], int(row["row_index"]), int(row["column_index"])))
    operator_digest = grouped_digest(
        b"MLS-MECHANICAL-OBSERVABILITY-OPERATOR-v1", module.OPERATOR_ENTRY_FIELDS, entries
    )

    def status(
        operator_id: str,
        observable: str,
        build: str,
        rows: int,
        columns: int,
        raw: bool,
        relation_count: int = 0,
        candidate: str = "A",
    ) -> dict[str, str]:
        return dict(
            zip(
                module.OPERATOR_STATUS_FIELDS,
                (
                    operator_id, configuration_id, candidate, "smoke_control", observable, build,
                    "4", str(relation_count), str(rows), str(columns), str(raw).lower(),
                    operator_digest if raw else "NA", "true", "NA", "false", "false",
                    "true", "false", "false",
                ),
                strict=True,
            )
        )

    statuses = [
        status("A_derivative", "frozen_quadratic_symmetric_gradient", "empty", 0, 0, False),
        status("A_gauge", "frozen_quadratic_gauge", "empty", 0, 0, False),
        status("A_sampling", "frozen_quadratic_sampling", "empty", 0, 0, False),
        status(
            "C_tetrahedron", "central_bond_length_rate", "built", 6, 12, True,
            relation_count=6, candidate="C",
        ),
    ]
    statuses.sort(key=lambda row: row["operator_id"])

    zero_metric = (
        "C_tetrahedron", "affine:smoke:detail", "affine_detail", "translation", "NA", "NA",
        "ALL", hx(0), hx(0), hx(0), hx(1), hx(0), "0", hx(1), "true", "m_per_s",
    )
    finite_operations = 12
    epsilon64 = 2.0**-52
    finite_bound = (
        256.0 * (finite_operations * epsilon64 / (1.0 - finite_operations * epsilon64))
        + 256.0 * sys.float_info.min
    )
    finite_metric = (
        "C_tetrahedron", "finite:smoke:length", "finite_bond_length", "proper_rotation", "NA",
        "bond_1_2", "length", hx(1), hx(1), hx(0), hx(1), hx(0),
        str(finite_operations), hx(finite_bound), "true", "m",
    )
    affine_rows = [
        dict(zip(module.AFFINE_OBJECTIVITY_FIELDS, values, strict=True))
        for values in (zero_metric, finite_metric)
    ]
    affine_rows.sort(key=lambda row: (row["operator_id"], row["test_id"]))
    invariance = [
        dict(
            zip(
                module.INVARIANCE_FIELDS,
                (
                    "identity_C_tetrahedron", "C_tetrahedron", "C_tetrahedron", "identity", hx(1),
                    "p000", "true", "true", "true", "true", hx(0), hx(0), hx(1), "true", "true",
                ),
                strict=True,
            )
        )
    ]
    grid_gauge = [
        dict(
            zip(
                module.GRID_GAUGE_FIELDS,
                (
                    "A_gauge", "A_sampling", "A_derivative", "0", "x", hx(0), hx(1), hx(1),
                    hx(1e-12), hx(1e12), "true", "true", "true", "false",
                ),
                strict=True,
            )
        )
    ]
    exact_reference = [
        dict(
            zip(
                module.EXACT_REFERENCE_FIELDS,
                (
                    "tetrahedron_k4", configuration_id, "C", "C_tetrahedron", "Fraction_RREF", "0",
                    "6", "12", "6", "6", "6", "0", "true", "true",
                    "independent_fraction_rref", "true", "false",
                ),
                strict=True,
            )
        )
    ]
    tables = {
        "configurations.csv": configurations,
        "packets.csv": packets,
        "neighbor_pairs.csv": neighbors,
        "relations.csv": relations,
        "operator_status.csv": statuses,
        "operator_entries.csv": entries,
        "moment_diagnostics.csv": [],
        "affine_objectivity.csv": affine_rows,
        "invariance.csv": invariance,
        "rigid_basis.csv": [],
        "rank_status.csv": [],
        "nullspace_modes.csv": [],
        "nullspace_metrics.csv": [],
        "grid_gauge.csv": grid_gauge,
        "exact_reference.csv": exact_reference,
    }
    for name, rows in tables.items():
        write_csv(bundle / name, module.CSV_SCHEMAS[name], rows)
    summary = {
        "schema": module.SUMMARY_SCHEMA,
        "mode": "smoke",
        "provisional": True,
        "sweep_complete": False,
        "producer": module.PRODUCER,
        "seed": module.SEED,
        "source_sha": SOURCE_SHA,
        "parent_sha": PARENT_SHA,
        "branch": module.BRANCH,
        "dirty": False,
        "registered_configuration_ids": [configuration_id],
        "registered_operator_ids": [row["operator_id"] for row in statuses],
        "checkpoint_round_trip_all_pass": True,
        "diagnostics_read_only_all_exact": True,
        "neighbor_lookup_all_agree": True,
        "negative_control_reproduced": True,
        "affine_objectivity_all_pass": True,
        "finite_objectivity_all_pass": True,
        "invariance_all_pass": True,
        "decisive_rank_rows_all_unambiguous": True,
        "raw_decision_rows_all_exported": True,
        "independent_reference_all_pass": True,
        "nondeterminism_detected": False,
        "candidate_findings": {
            "A": "negative_control_reproduced",
            "B": "inconclusive",
            "C": "inconclusive",
            "D": "inconclusive",
        },
        "decision": "stop_inconclusive_or_implementation_failure",
        "promotion": False,
        "row_counts": {name: len(rows) for name, rows in tables.items()},
        "tolerances": module.EXPECTED_TOLERANCES,
    }
    write_json(bundle / "summary.json", summary)
    refresh_manifest(module, bundle)


def make_bundle(module: ModuleType, bundle: Path, *, operator_unit_only: bool = False) -> None:
    """Build a compact, independently mutable, schema-complete smoke bundle."""

    bundle.mkdir(parents=True)
    configuration_id = "exact.tetrahedron_k4"
    positions = {
        1: (Decimal(0), Decimal(0), Decimal(0)),
        2: (Decimal(1), Decimal(0), Decimal(0)),
        3: (Decimal(0), Decimal(1), Decimal(0)),
        4: (Decimal(0), Decimal(0), Decimal(1)),
    }
    packet_ids = sorted(positions)
    support = Decimal(2)
    packets = [
        dict(zip(module.PACKET_FIELDS, (
            configuration_id, str(index), str(packet_id), "4096",
            *(_decimal_hex(value) for value in positions[packet_id]),
            hx(0), hx(0), hx(0), hx(0), hx(0), hx(0),
        ), strict=True))
        for index, packet_id in enumerate(packet_ids)
    ]
    neighbors: list[dict[str, str]] = []
    for phase in module.LOOKUP_PHASES:
        for low, high in itertools.combinations(packet_ids, 2):
            offset = [positions[high][axis] - positions[low][axis] for axis in range(3)]
            distance_squared = module.decimal_dot(offset, offset)
            weight = (Decimal(1) - distance_squared / (support * support)) ** 2
            neighbors.append(dict(zip(module.NEIGHBOR_PAIR_FIELDS, (
                configuration_id, phase, str(low), str(high),
                _decimal_hex(distance_squared), _decimal_hex(support * support),
                "true", "true", "true", _decimal_hex(weight),
            ), strict=True)))
    edges = list(itertools.combinations(packet_ids, 2))
    relations: list[dict[str, str]] = []
    for relation_index, (first, second) in enumerate(edges):
        offset = [positions[second][axis] - positions[first][axis] for axis in range(3)]
        length = module.decimal_dot(offset, offset).sqrt()
        relations.append(dict(zip(module.RELATION_FIELDS, (
            configuration_id, str(relation_index), f"bond.{first}.{second}", "bond",
            "NA", str(first), str(second), "NA", "retained", "exact_control",
            _decimal_hex(length), "m", "NA",
        ), strict=True)))
    relation_ids = [row["relation_id"] for row in relations]

    b_matrix_source, reconstructed_moments = module.reconstruct_corrected_gradient(
        positions, support
    )
    c_matrix_source = module.bond_rows_decimal(positions, packet_ids, relations)

    def quantized(matrix: Sequence[Sequence[Decimal]]) -> list[list[Decimal]]:
        return [[Decimal.from_float(float(value)) for value in row] for row in matrix]

    b_matrix, c_matrix = quantized(b_matrix_source), quantized(c_matrix_source)
    b_id, c_id, d_id = (
        f"{configuration_id}.B", f"{configuration_id}.C", f"{configuration_id}.D"
    )
    entries = [
        *_operator_rows(module, b_id, "B", b_matrix_source, packet_ids, relation_ids),
        *_operator_rows(module, c_id, "C", c_matrix_source, packet_ids, relation_ids),
    ]
    entries.sort(key=lambda row: (
        row["operator_id"], int(row["row_index"]), int(row["column_index"])
    ))
    entries_by_operator = {
        operator_id: [row for row in entries if row["operator_id"] == operator_id]
        for operator_id in (b_id, c_id)
    }

    def operator_digest(operator_id: str) -> str:
        return grouped_digest(
            b"MLS-MECHANICAL-OBSERVABILITY-OPERATOR-v1",
            module.OPERATOR_ENTRY_FIELDS,
            entries_by_operator[operator_id],
        )

    def built_status(
        operator_id: str, candidate: str, role: str, observable: str,
        row_count: int, relation_count: int,
    ) -> dict[str, str]:
        return dict(zip(module.OPERATOR_STATUS_FIELDS, (
            operator_id, configuration_id, candidate, role, observable, "built", "4",
            str(relation_count), str(row_count), "12", "true",
            operator_digest(operator_id), "true", "NA", "true",
            str(candidate == "B").lower(), "true", "true", "false",
            "NA", "NA", "NA", "NA", "NA", "NA", "NA",
        ), strict=True))

    statuses = [
        built_status(
            b_id, "B", "corrected_local_gradient", "corrected_local_symmetric_gradient", 24, 0
        ),
        built_status(c_id, "C", "central_relation_graph", "central_bond_length_rate", 6, 6),
        dict(zip(module.OPERATOR_STATUS_FIELDS, (
            d_id, configuration_id, "D", "objective_volume_enrichment",
            "enriched_bond_and_volume", "not_triggered", "4", "6", "0", "0",
            "false", "NA", "false", "NA", "false", "false", "true", "false", "false",
            "not_attempted", "global_d_not_triggered", "NA", "NA", "NA", "NA", "none",
        ), strict=True)),
    ]
    statuses.sort(key=lambda row: row["operator_id"])

    moment_rows: list[dict[str, str]] = []
    inverse_tolerance = Decimal(4096) * Decimal(3) * module.EPS64
    for packet_id in packet_ids:
        item = reconstructed_moments[packet_id]
        moment = item["moment"]
        inverse = item["inverse"]
        assert inverse is not None
        eigenvalues = module.symmetric_eigenvalues3_decimal(moment)
        condition = eigenvalues[-1] / eigenvalues[0]
        inverse_error = [
            [module.dsum(moment[row][inner] * inverse[inner][column] for inner in range(3))
             - (Decimal(1) if row == column else Decimal(0)) for column in range(3)]
            for row in range(3)
        ]
        inverse_residual = module.decimal_matrix_norm(inverse_error) / max(
            Decimal(1),
            module.decimal_matrix_norm(moment) * module.decimal_matrix_norm(inverse),
        )
        symmetry = module.decimal_norm(
            moment[row][column] - moment[column][row]
            for row in range(3) for column in range(3)
        ) / max(module.decimal_matrix_norm(moment), module.MIN_NORMAL)
        values = [moment[row][column] for row in range(3) for column in range(3)]
        moment_rows.append(dict(zip(module.MOMENT_DIAGNOSTIC_FIELDS, (
            b_id, str(packet_id), str(item["neighbor_count"]),
            *(_decimal_hex(value) for value in values), _decimal_hex(symmetry),
            _decimal_hex(eigenvalues[0]), _decimal_hex(eigenvalues[-1]),
            _decimal_hex(condition), "dense_symmetric_eigen_estimate",
            _decimal_hex(inverse_residual), _decimal_hex(inverse_tolerance),
            "built", "true",
        ), strict=True)))

    if operator_unit_only:
        packet_digest = grouped_digest(
            b"MLS-MECHANICAL-OBSERVABILITY-PACKETS-v1", module.PACKET_FIELDS, packets
        )
        neighbor_digest = grouped_digest(
            b"MLS-MECHANICAL-OBSERVABILITY-NEIGHBORS-v1",
            module.NEIGHBOR_PAIR_FIELDS,
            neighbors,
        )
        relation_digest = grouped_digest(
            b"MLS-MECHANICAL-OBSERVABILITY-RELATIONS-v1",
            module.RELATION_FIELDS,
            relations,
        )
        empty_checkpoint = hashlib.sha256(b"").hexdigest()
        configurations = [dict(zip(module.CONFIGURATION_FIELDS, (
            configuration_id, configuration_id, "tetrahedron_k4", "original", "exact",
            "identity", "p000", "4", hx(0.25), hx(2), hx(1), "3", "true", "6",
            "6", "3", "6", "true", "false", "true", packet_digest, neighbor_digest,
            relation_digest, empty_checkpoint, empty_checkpoint, "true",
        ), strict=True))]
        for name, rows in {
            "configurations.csv": configurations,
            "packets.csv": packets,
            "relations.csv": relations,
            "operator_status.csv": statuses,
            "operator_entries.csv": entries,
            "moment_diagnostics.csv": moment_rows,
            "grid_nodes.csv": [],
        }.items():
            write_csv(bundle / name, module.CSV_SCHEMAS[name], rows)
        return

    rank_rows: list[dict[str, str]] = []
    rigid_rows: list[dict[str, str]] = []
    null_rows: list[dict[str, str]] = []
    metric_rows: list[dict[str, str]] = []
    rank_info: dict[str, dict[str, int | Decimal]] = {}

    for operator_id, matrix in ((b_id, b_matrix), (c_id, c_matrix)):
        normalized = module.normalized_rows(matrix)
        permutation, diagonals = module.decimal_householder_qrcp_trace(normalized)
        first_diagonal = diagonals[0]
        threshold = (
            Decimal(512) * Decimal(max(len(normalized), len(normalized[0])))
            * module.EPS64 * max(first_diagonal, module.MIN_NORMAL)
        )
        lower, upper = threshold / Decimal(8), threshold * Decimal(8)
        accepted = [value > threshold for value in diagonals]
        rank = sum(accepted)
        nullity = len(normalized[0]) - rank
        assert rank == 6 and nullity == 6
        residual_tolerance = (
            Decimal(4096) * Decimal(max(len(normalized), len(normalized[0]))) * module.EPS64
        )
        rigid_raw = module.expected_rigid_generators_decimal(positions)
        rigid_q = module.orthonormalize_columns(rigid_raw, Decimal("1e-40"))
        complete = rigid_q
        normalized_rigid = _normalized_product(module, normalized, rigid_q)
        normalized_null = _normalized_product(module, normalized, complete)
        aggregate = {
            "normalized_rigid_residual": normalized_rigid,
            "normalized_null_residual": normalized_null,
            "normalized_nonrigid_residual": Decimal(0),
            "rigid_orthogonality_residual": Decimal(0),
        }
        invariant = (
            "analyzed", str(len(normalized)), str(len(normalized[0])), str(rank),
            str(nullity), "6", "0", _decimal_hex(threshold), _decimal_hex(lower),
            _decimal_hex(upper), "false",
            "binary64_householder_qrcp_threshold_estimate", "false", "true", "true",
            "true", _decimal_hex(normalized_rigid), _decimal_hex(normalized_null), hx(0), hx(0),
            _decimal_hex(residual_tolerance), "true", "false", "NA", "NA",
        )
        rank_rows.append(dict(zip(module.RANK_STATUS_FIELDS, (
            operator_id, "summary", "NA", "NA", "NA", "NA", *invariant,
        ), strict=True)))
        for step, (column, diagonal, is_accepted) in enumerate(zip(
            permutation, diagonals, accepted, strict=True
        )):
            rank_rows.append(dict(zip(module.RANK_STATUS_FIELDS, (
                operator_id, "pivot", str(step), str(column), _decimal_hex(diagonal),
                str(is_accepted).lower(), *invariant,
            ), strict=True)))
        for basis_kind, columns in (("raw_generator", rigid_raw), ("orthonormal", rigid_q)):
            for mode_index, column in enumerate(columns):
                for dof_index, value in enumerate(column):
                    rigid_rows.append(dict(zip(module.RIGID_BASIS_FIELDS, (
                        operator_id, basis_kind, str(mode_index), str(dof_index), "packet",
                        str(packet_ids[dof_index // 3]), module.AXES[dof_index % 3],
                        _decimal_hex(value),
                    ), strict=True)))
        for mode_index, column in enumerate(complete):
            for dof_index, value in enumerate(column):
                null_rows.append(dict(zip(module.NULLSPACE_MODE_FIELDS, (
                    operator_id, "complete_kernel", str(mode_index), str(dof_index), "packet",
                    str(packet_ids[dof_index // 3]), module.AXES[dof_index % 3],
                    _decimal_hex(value),
                ), strict=True)))
            image = module.decimal_norm(module.decimal_matvec(normalized, column))
            denominator = max(
                module.decimal_matrix_norm(normalized) * module.decimal_norm(column),
                module.MIN_NORMAL,
            )
            normalized_error = image / denominator
            projection = module.decimal_norm(
                module.decimal_dot(rigid_mode, column) for rigid_mode in rigid_q
            )
            metric_rows.append(dict(zip(module.NULLSPACE_METRIC_FIELDS, (
                operator_id, "complete_kernel", str(mode_index), _decimal_hex(image),
                _decimal_hex(denominator), _decimal_hex(normalized_error),
                _decimal_hex(projection), hx(0), _decimal_hex(residual_tolerance),
                "true", "false",
            ), strict=True)))
        rank_info[operator_id] = {
            "rank": rank, "nullity": nullity,
            "snapshot_residual": max(aggregate.values()),
        }

    rank_rows.sort(key=lambda row: (
        row["operator_id"], 0 if row["record_kind"] == "summary" else 1,
        -1 if row["pivot_step"] == "NA" else int(row["pivot_step"]),
    ))
    rigid_rows.sort(key=lambda row: (
        row["operator_id"], row["basis_kind"], int(row["mode_index"]), int(row["dof_index"])
    ))
    null_rows.sort(key=lambda row: (
        row["operator_id"], row["basis_kind"], int(row["mode_index"]), int(row["dof_index"])
    ))
    metric_rows.sort(key=lambda row: (
        row["operator_id"], row["basis_kind"], int(row["mode_index"])
    ))

    affine_rows: list[dict[str, str]] = []
    matrices = {b_id: b_matrix, c_id: c_matrix}
    for operator_id, candidate in ((b_id, "B"), (c_id, "C")):
        matrix = matrices[operator_id]
        bound = Decimal(4096) * Decimal(max(len(matrix), len(matrix[0]))) * module.EPS64
        for field, (gradient, intercept) in module.AFFINE_FIELDS.items():
            velocity = [
                component for packet_id in packet_ids
                for component in module.affine_velocity(gradient, intercept, positions[packet_id])
            ]
            measured = module.decimal_matvec(matrix, velocity)
            target = module.affine_target(candidate, gradient, positions, relations)
            error = module.decimal_norm(module.vector_subtract(measured, target))
            scale = max(
                module.decimal_matrix_norm(matrix) * module.decimal_norm(velocity)
                + module.decimal_norm(target), module.MIN_NORMAL,
            )
            affine_rows.append(dict(zip(module.AFFINE_OBJECTIVITY_FIELDS, (
                operator_id, f"affine:{field}:aggregate", "linear_operator_aggregate",
                field, "NA", "NA", "ALL", _decimal_hex(module.decimal_norm(measured)),
                _decimal_hex(module.decimal_norm(target)), _decimal_hex(error),
                _decimal_hex(scale), _decimal_hex(error / scale), "0", _decimal_hex(bound),
                "true", "per_s" if candidate == "B" else "m_per_s",
            ), strict=True)))
            if candidate == "B":
                _unused, local_data = module.reconstruct_corrected_gradient(positions, support)
                velocities = {
                    packet_id: module.affine_velocity(gradient, intercept, positions[packet_id])
                    for packet_id in packet_ids
                }
                for packet_id in packet_ids:
                    coefficient = local_data[packet_id]["coefficient"]
                    for tensor_row in range(3):
                        for tensor_column in range(3):
                            measured_value = module.dsum(
                                velocities[source][tensor_row] * coefficient[source][tensor_column]
                                for source in packet_ids if source in coefficient
                            )
                            target_value = gradient[tensor_row][tensor_column]
                            absolute = abs(measured_value - target_value)
                            normalization = max(
                                Decimal(1), abs(measured_value), abs(target_value)
                            )
                            component = f"{tensor_row}{tensor_column}"
                            affine_rows.append(dict(zip(module.AFFINE_OBJECTIVITY_FIELDS, (
                                operator_id,
                                f"affine:{field}:full_gradient:{packet_id}:{component}",
                                "full_gradient_reproduction", field, str(packet_id), "NA",
                                component, _decimal_hex(measured_value), _decimal_hex(target_value),
                                _decimal_hex(absolute), _decimal_hex(normalization),
                                _decimal_hex(absolute / normalization), "0", _decimal_hex(bound),
                                str(absolute / normalization <= bound).lower(), "per_s",
                            ), strict=True)))

    transform_specs = {
        "proper_quaternion_rotation": (module.ROTATION_Q, (0, 0, 0), Decimal(1)),
        "signed_axis_rotation": (((1, 0, 0), (0, -1, 0), (0, 0, -1)), (0, 0, 0), Decimal(1)),
        "translation": (((1, 0, 0), (0, 1, 0), (0, 0, 1)), module.TRANSLATION_Q, Decimal(1)),
        "scale_half": (((1, 0, 0), (0, 1, 0), (0, 0, 1)), (0, 0, 0), Decimal("0.5")),
        "scale_double": (((1, 0, 0), (0, 1, 0), (0, 0, 1)), (0, 0, 0), Decimal(2)),
    }
    for name, (rotation_raw, translation_raw, scale) in transform_specs.items():
        rotation = [[Decimal(value.numerator) / Decimal(value.denominator)
                     if hasattr(value, "numerator") else Decimal(value)
                     for value in row] for row in rotation_raw]
        translation = [Decimal(value.numerator) / Decimal(value.denominator)
                       if hasattr(value, "numerator") else Decimal(value)
                       for value in translation_raw]
        transformed = {
            packet_id: tuple(
                scale * module.decimal_dot(rotation[axis], positions[packet_id]) + translation[axis]
                for axis in range(3)
            ) for packet_id in packet_ids
        }
        for relation in relations:
            first, second = int(relation["first_id"]), int(relation["second_id"])
            reference = module.decimal_norm(module.vector_subtract(positions[second], positions[first]))
            measured = module.decimal_norm(module.vector_subtract(transformed[second], transformed[first]))
            target = scale * reference
            absolute = abs(measured - target)
            magnitude = max(abs(measured), abs(target), module.MIN_NORMAL)
            operations = 16
            gamma = Decimal(operations) * module.EPS64 / (Decimal(1) - Decimal(operations) * module.EPS64)
            roundoff = Decimal(256) * gamma * magnitude + Decimal(256) * module.MIN_NORMAL
            relation_id = relation["relation_id"]
            affine_rows.append(dict(zip(module.AFFINE_OBJECTIVITY_FIELDS, (
                c_id, f"finite:{name}:{relation_id}", "finite_bond_length", name,
                "NA", relation_id, "length", _decimal_hex(measured), _decimal_hex(target),
                _decimal_hex(absolute), _decimal_hex(magnitude), _decimal_hex(absolute / magnitude),
                str(operations), _decimal_hex(roundoff), str(absolute <= roundoff).lower(), "m",
            ), strict=True)))
    affine_rows.sort(key=lambda row: (row["operator_id"], row["test_id"]))

    invariance_rows: list[dict[str, str]] = []
    for operator_id in (b_id, c_id):
        status = next(row for row in statuses if row["operator_id"] == operator_id)
        tolerance = Decimal(16384) * Decimal(max(
            int(status["row_count"]), int(status["column_count"])
        )) * module.EPS64
        invariance_rows.append(dict(zip(module.INVARIANCE_FIELDS, (
            f"permutation.{operator_id}", operator_id, operator_id, "packet_permutation",
            hx(1), "NA", "true", "true", "true", "true", hx(0), hx(0),
            _decimal_hex(tolerance), "true", "true",
        ), strict=True)))
    c_status = next(row for row in statuses if row["operator_id"] == c_id)
    c_tolerance = Decimal(16384) * Decimal(max(
        int(c_status["row_count"]), int(c_status["column_count"])
    )) * module.EPS64
    invariance_rows.append(dict(zip(module.INVARIANCE_FIELDS, (
        f"lookup_phase.{configuration_id}", c_id, c_id, "lookup_phase", hx(1),
        "p000_to_p037_011_029", "true", "true", "true", "true", hx(0), hx(0),
        _decimal_hex(c_tolerance), "false", "true",
    ), strict=True)))
    invariance_rows.sort(key=lambda row: row["comparison_id"])

    permutation_controls: list[dict[str, str]] = []
    permutation_entries: list[dict[str, str]] = []
    expected_order = module.packet_permutation(configuration_id, packet_ids)
    order_text = ":".join(str(value) for value in expected_order)
    for operator_id in (b_id, c_id):
        control_id = f"permutation.{operator_id}"
        alternate_group = []
        for entry in entries_by_operator[operator_id]:
            alternate = {"control_id": control_id, **entry}
            alternate_group.append(alternate)
            permutation_entries.append(alternate)
        matrix = matrices[operator_id]
        canonical_hash = hashlib.sha256(module.canonical_operator_payload(matrix)).hexdigest()
        raw_hash = grouped_digest(
            b"MLS-MECHANICAL-OBSERVABILITY-PERMUTATION-OPERATOR-v1",
            module.PERMUTATION_ENTRY_FIELDS,
            alternate_group,
        )
        permutation_controls.append(dict(zip(module.PERMUTATION_CONTROL_FIELDS, (
            control_id, operator_id, configuration_id, "sha256_packet_permutation_v1",
            str(module.SEED), order_text, str(len(matrix)), str(len(matrix[0])),
            str(len(alternate_group)), raw_hash, canonical_hash, canonical_hash,
            "true", "false",
        ), strict=True)))
    permutation_controls.sort(key=lambda row: row["control_id"])
    permutation_entries.sort(key=lambda row: (
        row["control_id"], int(row["row_index"]), int(row["column_index"])
    ))

    exact_reference = [dict(zip(module.EXACT_REFERENCE_FIELDS, (
        "tetrahedron_k4", configuration_id, "C", c_id, "Fraction_RREF", "0",
        "6", "12", "6", "6", "6", "0", "true", "true",
        "independent_fraction_rref", "true", "false",
    ), strict=True))]

    checkpoint = bytearray(b"MLSMOBS1")
    checkpoint.extend(struct.pack("<I", 1))
    checkpoint.extend(struct.pack("<dQ", float(support), len(packet_ids)))
    for packet_id in packet_ids:
        checkpoint.extend(struct.pack("<Qq", packet_id, 4096))
        checkpoint.extend(struct.pack("<6d", *(float(value) for value in positions[packet_id]), 0, 0, 0))
    checkpoint.extend(struct.pack("<Q", len(edges)))
    for first, second in edges:
        checkpoint.extend(struct.pack("<QQ", first, second))
    checkpoint.extend(struct.pack("<Q", 0))
    checkpoint_digest = hashlib.sha256(checkpoint).hexdigest()
    checkpoints = [dict(zip(module.CHECKPOINT_FIELDS, (
        configuration_id, "authoritative_input", "lowercase_hex", str(len(checkpoint)),
        checkpoint_digest, checkpoint.hex(),
    ), strict=True))]

    packet_digest = grouped_digest(
        b"MLS-MECHANICAL-OBSERVABILITY-PACKETS-v1", module.PACKET_FIELDS, packets
    )
    neighbor_digest = grouped_digest(
        b"MLS-MECHANICAL-OBSERVABILITY-NEIGHBORS-v1", module.NEIGHBOR_PAIR_FIELDS, neighbors
    )
    relation_digest = grouped_digest(
        b"MLS-MECHANICAL-OBSERVABILITY-RELATIONS-v1", module.RELATION_FIELDS, relations
    )
    configurations = [dict(zip(module.CONFIGURATION_FIELDS, (
        configuration_id, configuration_id, "tetrahedron_k4", "original", "exact",
        "identity", "p000", "4", hx(0.25), hx(2), hx(1), "3", "true", "6",
        "6", "3", "6", "true", "false", "true", packet_digest, neighbor_digest,
        relation_digest, checkpoint_digest, checkpoint_digest, "true",
    ), strict=True))]

    tables = {
        "configurations.csv": configurations,
        "packets.csv": packets,
        "neighbor_pairs.csv": neighbors,
        "relations.csv": relations,
        "operator_status.csv": statuses,
        "operator_entries.csv": entries,
        "moment_diagnostics.csv": moment_rows,
        "affine_objectivity.csv": affine_rows,
        "invariance.csv": invariance_rows,
        "rigid_basis.csv": rigid_rows,
        "rank_status.csv": rank_rows,
        "nullspace_modes.csv": null_rows,
        "nullspace_metrics.csv": metric_rows,
        "grid_gauge.csv": [],
        "exact_reference.csv": exact_reference,
        "grid_nodes.csv": [],
        "checkpoints.csv": checkpoints,
        "permutation_controls.csv": permutation_controls,
        "permutation_entries.csv": permutation_entries,
    }
    for name, rows in tables.items():
        write_csv(bundle / name, module.CSV_SCHEMAS[name], rows)
    summary = {
        "schema": module.SUMMARY_SCHEMA,
        "mode": "smoke",
        "provisional": True,
        "sweep_complete": False,
        "producer": module.PRODUCER,
        "seed": module.SEED,
        "source_sha": SOURCE_SHA,
        "parent_sha": PARENT_SHA,
        "branch": module.BRANCH,
        "dirty": False,
        "registered_configuration_ids": [configuration_id],
        "registered_operator_ids": [row["operator_id"] for row in statuses],
        "checkpoint_round_trip_all_pass": True,
        "diagnostics_read_only_all_exact": True,
        "neighbor_lookup_all_agree": True,
        "negative_control_reproduced": False,
        "affine_objectivity_all_pass": True,
        "finite_objectivity_all_pass": True,
        "invariance_all_pass": True,
        "decisive_rank_rows_all_unambiguous": True,
        "raw_decision_rows_all_exported": True,
        "independent_reference_all_pass": True,
        "nondeterminism_detected": False,
        "candidate_findings": {
            "A": "negative_control_failed", "B": "inconclusive",
            "C": "inconclusive", "D": "inconclusive",
        },
        "decision": "stop_inconclusive_or_implementation_failure",
        "promotion": False,
        "row_counts": {name: len(rows) for name, rows in tables.items()},
        "tolerances": module.EXPECTED_TOLERANCES,
    }
    write_json(bundle / "summary.json", summary)
    refresh_manifest(module, bundle)


def run_validator(
    validator: Path,
    bundle: Path,
    compare: Path | None = None,
    findings: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, str(validator), "--bundle", str(bundle), "--allow-smoke"]
    if compare is not None:
        command.extend(("--compare", str(compare)))
    if findings is not None:
        command.extend(("--findings-output", str(findings)))
    return subprocess.run(command, check=False, capture_output=True, text=True, timeout=300)


def mutate_csv(bundle: Path, name: str, change: Callable[[list[dict[str, str]]], None]) -> None:
    fields, rows = read_csv(bundle / name)
    change(rows)
    write_csv(bundle / name, fields, rows)


def exercise_decision_state_machine(module: ModuleType) -> int:
    """Exercise every nullable decision-rank state without bundle I/O.

    These cases intentionally keep producer summary gates optimistic unless a
    case is specifically about a reference failure.  The reducer must derive
    its own implementation stop from operator/rank state before it reads any
    nullable non-rigid quotient.
    """

    configuration_id = "base.sc3.r180.original"

    def operator_id(candidate: str) -> str:
        return f"{configuration_id}.{candidate}"

    sampling_id = f"{configuration_id}.A.p000.S"
    derivative_id = f"{configuration_id}.A.p000.D"
    required_flags = (
        "checkpoint_round_trip_all_pass",
        "diagnostics_read_only_all_exact",
        "neighbor_lookup_all_agree",
        "affine_objectivity_all_pass",
        "finite_objectivity_all_pass",
        "invariance_all_pass",
        "decisive_rank_rows_all_unambiguous",
        "raw_decision_rows_all_exported",
        "independent_reference_all_pass",
    )
    summary = {
        "mode": "full",
        "nondeterminism_detected": False,
        **{field: True for field in required_flags},
    }
    status = {
        sampling_id: {
            "candidate": "A", "configuration_id": configuration_id,
            "build_status": "built", "decision_driving": "true",
            "rank_applicable": "true", "b_rank_eligible": "false",
            "row_normalization_complete": "true", "raw_exported": "true",
        },
        derivative_id: {
            "candidate": "A", "configuration_id": configuration_id,
            "build_status": "built", "decision_driving": "true",
            "rank_applicable": "false", "b_rank_eligible": "false",
            "row_normalization_complete": "true", "raw_exported": "true",
        },
        operator_id("B"): {
            "candidate": "B", "configuration_id": configuration_id,
            "build_status": "built", "decision_driving": "true",
            "rank_applicable": "true", "b_rank_eligible": "true",
            "row_normalization_complete": "true", "raw_exported": "true",
        },
        operator_id("C"): {
            "candidate": "C", "configuration_id": configuration_id,
            "build_status": "built", "decision_driving": "true",
            "rank_applicable": "true", "b_rank_eligible": "false",
            "row_normalization_complete": "true", "raw_exported": "true",
        },
        operator_id("D"): {
            "candidate": "D", "configuration_id": configuration_id,
            "build_status": "not_triggered", "decision_driving": "false",
            "rank_applicable": "false", "b_rank_eligible": "false",
            "row_normalization_complete": "false", "raw_exported": "false",
        },
    }

    def resolved(nonrigid: int, generic_pass: bool) -> dict[str, Any]:
        return {
            "status": "analyzed", "ambiguous": False,
            "basis_complete": True, "contract_pass": True,
            "generic_pass": generic_pass, "nonrigid_nullity": nonrigid,
        }

    ranks = {
        sampling_id: resolved(3, False),
        operator_id("B"): resolved(1, False),
        operator_id("C"): resolved(0, True),
    }
    generic = {configuration_id}

    findings, decision = module.derive_decision(
        summary, status, ranks, True, generic
    )
    if decision != "retain_central_relational_representation_for_research" \
            or findings["B"] \
            != "reject_averaged_single_gradient_packet_kinematics":
        raise AssertionError("resolved B/C decision control did not remain conclusive")
    cases = 1

    def expect_stop(
        label: str,
        case_summary: Mapping[str, Any],
        case_status: Mapping[str, Mapping[str, str]],
        case_ranks: Mapping[str, Mapping[str, Any]],
        negative_control: bool = True,
    ) -> None:
        try:
            case_findings, case_decision = module.derive_decision(
                case_summary, case_status, case_ranks, negative_control, generic
            )
        except Exception as error:  # pragma: no cover - diagnostic detail
            raise AssertionError(f"{label} raised before implementation STOP") from error
        if case_decision != "stop_inconclusive_or_implementation_failure" \
                or any(case_findings[candidate] != "inconclusive"
                       for candidate in ("B", "C", "D")):
            raise AssertionError(f"{label} reached a scientific decision")

    unavailable_rank_states = {
        "ambiguous": {
            "status": "ambiguous", "ambiguous": True,
            "basis_complete": False, "contract_pass": False,
            "generic_pass": None, "nonrigid_nullity": None,
        },
        "numerical_failure": {
            "status": "numerical_failure", "ambiguous": False,
            "basis_complete": False, "contract_pass": False,
            "generic_pass": None, "nonrigid_nullity": None,
        },
        "rigid_containment_failure": {
            "status": "analyzed", "ambiguous": False,
            "basis_complete": True, "contract_pass": False,
            "generic_pass": False, "nonrigid_nullity": None,
        },
        "claimed_contract_missing_quotient": {
            "status": "analyzed", "ambiguous": False,
            "basis_complete": True, "contract_pass": True,
            "generic_pass": False, "nonrigid_nullity": None,
        },
    }

    # B and C share the no-D control.  Every unresolved rank must stop before
    # accessing its nullable quotient, even if all producer summary flags claim
    # success.
    for candidate in ("B", "C"):
        for state_name, rank_state in unavailable_rank_states.items():
            case_ranks = copy.deepcopy(ranks)
            case_ranks[operator_id(candidate)] = copy.deepcopy(rank_state)
            expect_stop(
                f"generic {candidate} {state_name}", summary, status, case_ranks
            )
            cases += 1

        case_summary = dict(summary)
        case_summary["independent_reference_all_pass"] = False
        expect_stop(
            f"generic {candidate} reference failure",
            case_summary, status, ranks,
        )
        cases += 1

        case_status = copy.deepcopy(status)
        candidate_status = case_status[operator_id(candidate)]
        candidate_status.update({
            "build_status": "numerical_failure",
            "rank_applicable": "false",
            "row_normalization_complete": "false",
            "raw_exported": "false",
        })
        if candidate == "B":
            candidate_status["b_rank_eligible"] = "false"
        case_ranks = copy.deepcopy(ranks)
        del case_ranks[operator_id(candidate)]
        expect_stop(
            f"generic {candidate} unbuilt", summary, case_status, case_ranks
        )
        cases += 1

    # Trigger D with a resolved non-rigid C, then exercise the same complete
    # built/resolved and unavailable states for the enriched relation operator.
    triggered_status = copy.deepcopy(status)
    triggered_status[operator_id("D")].update({
        "build_status": "built", "decision_driving": "true",
        "rank_applicable": "true", "row_normalization_complete": "true",
        "raw_exported": "true",
    })
    triggered_ranks = copy.deepcopy(ranks)
    triggered_ranks[operator_id("C")] = resolved(1, False)
    triggered_ranks[operator_id("D")] = resolved(0, True)
    findings, decision = module.derive_decision(
        summary, triggered_status, triggered_ranks, True, generic
    )
    if decision != "retain_volume_enriched_relational_representation_for_research" \
            or findings["D"] \
            != "retain_volume_enriched_relational_representation_for_research":
        raise AssertionError("resolved D decision control did not remain conclusive")
    cases += 1

    for state_name, rank_state in unavailable_rank_states.items():
        case_ranks = copy.deepcopy(triggered_ranks)
        case_ranks[operator_id("D")] = copy.deepcopy(rank_state)
        expect_stop(
            f"generic D {state_name}", summary, triggered_status, case_ranks
        )
        cases += 1
    reference_summary = dict(summary)
    reference_summary["independent_reference_all_pass"] = False
    expect_stop(
        "generic D reference failure", reference_summary,
        triggered_status, triggered_ranks,
    )
    cases += 1
    unbuilt_d_status = copy.deepcopy(triggered_status)
    unbuilt_d_status[operator_id("D")].update({
        "build_status": "numerical_failure", "rank_applicable": "false",
        "row_normalization_complete": "false", "raw_exported": "false",
    })
    unbuilt_d_ranks = copy.deepcopy(triggered_ranks)
    del unbuilt_d_ranks[operator_id("D")]
    expect_stop(
        "generic D unbuilt", summary, unbuilt_d_status, unbuilt_d_ranks
    )
    cases += 1

    # Candidate A's negative control is an implementation prerequisite.  Its
    # unresolved rank and both partial-pair build states must quarantine B/C/D
    # before scientific reduction as well.
    for state_name, rank_state in unavailable_rank_states.items():
        case_ranks = copy.deepcopy(ranks)
        case_ranks[sampling_id] = copy.deepcopy(rank_state)
        expect_stop(
            f"Candidate A {state_name}", summary, status, case_ranks, False
        )
        cases += 1
    for failed_id, partner_id in (
        (sampling_id, derivative_id), (derivative_id, sampling_id)
    ):
        case_status = copy.deepcopy(status)
        case_status[failed_id].update({
            "build_status": "numerical_failure", "rank_applicable": "false",
            "row_normalization_complete": "false",
        })
        case_status[partner_id]["rank_applicable"] = "false"
        case_ranks = copy.deepcopy(ranks)
        case_ranks.pop(sampling_id, None)
        expect_stop(
            f"Candidate A partial pair {failed_id}",
            summary, case_status, case_ranks, False,
        )
        cases += 1

    return cases


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    root = Path(__file__).resolve().parents[1]
    parser.add_argument(
        "--validator",
        type=Path,
        default=root / "reference" / "validate_mechanical_observability_bundle.py",
    )
    parser.add_argument("--skip-positive", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--decision-state-only", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    module = load_module(args.validator)
    decision_state_cases = exercise_decision_state_machine(module)
    if args.decision_state_only:
        print(
            "mechanical observability decision-state regression: PASS "
            f"({decision_state_cases} cases)"
        )
        return 0
    mutations = 0
    with tempfile.TemporaryDirectory(prefix="mls-mechanical-validator-") as temporary:
        root_path = Path(temporary)
        base = root_path / "base"
        twin = root_path / "twin"
        materialize_registered_smoke_fixture(module, base)
        mutations += decision_state_cases
        shutil.copytree(base, twin)
        if not args.skip_positive:
            positive_findings = root_path / "positive-findings.json"
            positive = run_validator(
                args.validator, base, twin, positive_findings
            )
            if positive.returncode != 0:
                raise AssertionError(
                    f"positive fixture rejected\n{positive.stdout}\n{positive.stderr}"
                )
            parsed_findings = json.loads(positive_findings.read_text(encoding="utf-8"))
            if parsed_findings["comparison_status"] != "byte_identical" \
                    or parsed_findings["decision"] \
                    != "stop_inconclusive_or_implementation_failure" \
                    or parsed_findings["promotion"]:
                raise AssertionError("positive findings artifact has wrong route")
            file_digest = hashlib.sha256(positive_findings.read_bytes()).hexdigest()
            if f"findings_sha256={file_digest}" not in positive.stdout:
                raise AssertionError("positive findings stdout digest mismatch")
            claimed_result_hash = parsed_findings.pop(
                "result_sha256_before_hash_field"
            )
            if hashlib.sha256(
                module.canonical_compact_json(parsed_findings)
            ).hexdigest() != claimed_result_hash:
                raise AssertionError("positive findings result pre-hash mismatch")

        authentic_pair_fixtures: dict[str, Path] = {}
        for failed_half in ("sampling", "derivative"):
            fixture = root_path / f"authentic-a-pair-{failed_half}-failure"
            findings_path = root_path / f"authentic-a-pair-{failed_half}-findings.json"
            shutil.copytree(base, fixture)
            materialize_authentic_a_pair_failure_fixture(
                module, fixture, failed_half
            )
            result = run_validator(
                args.validator, fixture, findings=findings_path
            )
            if result.returncode != 0:
                raise AssertionError(
                    f"authentic {failed_half} A-pair fixture rejected\n"
                    f"{result.stdout}\n{result.stderr}"
                )
            findings = json.loads(findings_path.read_text(encoding="utf-8"))
            gates = findings["derived_gates"]
            if findings["mode"] != "failure_fixture" \
                    or findings["comparison_status"] != "single" \
                    or findings["decision"] \
                    != "stop_inconclusive_or_implementation_failure" \
                    or findings["promotion"] \
                    or gates["negative_control_reproduced"] \
                    or gates["decisive_rank_rows_all_unambiguous"] \
                    or not gates["producer_claims_consistent"]:
                raise AssertionError(
                    f"authentic {failed_half} A-pair fixture escaped quarantine"
                )
            authentic_pair_fixtures[failed_half] = fixture
            mutations += 1

        # The frozen smoke fixture itself contains the A gauge, enriched D,
        # non-rigid C, and metamorphic branches.  The byte-identical positive
        # comparison above validates those branches once; mutation staging
        # reuses the same immutable source rather than paying for a duplicate
        # full high-precision pass.
        branch_fixture = base

        race_live = root_path / "snapshot-race-live"
        shutil.copytree(base, race_live)
        race_summary = json.loads((race_live / "summary.json").read_text(encoding="utf-8"))
        race_summary["promotion"] = True
        write_json(race_live / "summary.json", race_summary)
        refresh_manifest(module, race_live)
        race_snapshot = root_path / "snapshot-race-captured"
        race_signature = module.capture_bundle_snapshot(race_live, race_snapshot)
        invalid_bytes = {path.name: path.read_bytes() for path in race_live.iterdir()}
        for source in base.iterdir():
            (race_live / source.name).write_bytes(source.read_bytes())
        for name, payload in invalid_bytes.items():
            (race_live / name).write_bytes(payload)
        try:
            module.validate_snapshot_bundle(race_snapshot, allow_smoke=True)
        except module.InvalidBundle:
            pass
        else:
            raise AssertionError("replace/restore race changed captured validator semantics")
        module.require_live_bundle_unchanged(race_live, race_signature)
        mutations += 1

        changed_live = root_path / "snapshot-persistent-live-change"
        shutil.copytree(base, changed_live)
        changed_snapshot = root_path / "snapshot-persistent-captured"
        changed_signature = module.capture_bundle_snapshot(changed_live, changed_snapshot)
        (changed_live / "packets.csv").write_bytes(
            (changed_live / "packets.csv").read_bytes() + b"tamper\n"
        )
        try:
            module.require_live_bundle_unchanged(changed_live, changed_signature)
        except module.InvalidBundle:
            pass
        else:
            raise AssertionError("persistent live mutation escaped validator rescan")
        mutations += 1

        def reject(label: str, mutation: Callable[[Path], None], *, refresh: bool = True) -> None:
            nonlocal mutations
            if args.skip_positive:
                print(f"debug mutation: {label}", flush=True)
            target = root_path / label
            shutil.copytree(base, target)
            mutation(target)
            if refresh:
                refresh_manifest(module, target)
            result = run_validator(args.validator, target)
            if result.returncode == 0 or INVALID not in result.stderr:
                raise AssertionError(f"mutation {label} accepted\n{result.stdout}\n{result.stderr}")
            mutations += 1

        def reject_branch(label: str, mutation: Callable[[Path], None]) -> None:
            if args.skip_positive:
                print(f"debug branch mutation: {label}", flush=True)
            nonlocal mutations
            target = root_path / f"branch-{label}"
            shutil.copytree(branch_fixture, target)
            mutation(target)
            refresh_manifest(module, target)
            result = run_validator(args.validator, target)
            if result.returncode == 0 or INVALID not in result.stderr:
                raise AssertionError(
                    f"branch mutation {label} accepted\n{result.stdout}\n{result.stderr}"
                )
            mutations += 1

        def accept_stop(
            label: str,
            mutation: Callable[[Path], None],
            required_false_gate: str,
        ) -> None:
            nonlocal mutations
            if args.skip_positive:
                print(f"debug valid-negative: {label}", flush=True)
            target = root_path / label
            findings_path = root_path / f"{label}-findings.json"
            shutil.copytree(base, target)
            mutation(target)
            result = run_validator(args.validator, target, findings=findings_path)
            if result.returncode != 0:
                raise AssertionError(
                    f"valid-negative {label} rejected\n{result.stdout}\n{result.stderr}"
                )
            findings = json.loads(findings_path.read_text(encoding="utf-8"))
            if findings["decision"] != "stop_inconclusive_or_implementation_failure" \
                    or findings["promotion"] \
                    or findings["derived_gates"][required_false_gate]:
                raise AssertionError(f"valid-negative {label} did not force its STOP gate")
            mutations += 1

        def reject_pair_fixture(
            label: str, failed_half: str, mutation: Callable[[Path], None]
        ) -> None:
            nonlocal mutations
            target = root_path / label
            shutil.copytree(authentic_pair_fixtures[failed_half], target)
            mutation(target)
            refresh_summary_row_counts(module, target)
            refresh_manifest(module, target)
            result = run_validator(args.validator, target)
            if result.returncode == 0 or INVALID not in result.stderr:
                raise AssertionError(
                    f"malformed pair fixture {label} accepted\n"
                    f"{result.stdout}\n{result.stderr}"
                )
            mutations += 1

        def add_stray_pair_rank(bundle: Path) -> None:
            fields, rows = read_csv(bundle / "rank_status.csv")
            source_id = "base.filament.r205.original.A.p037_011_029.S"
            target_id = "base.filament.r205.original.A.p000.S"
            additions = [dict(row, operator_id=target_id) for row in rows
                         if row["operator_id"] == source_id]
            if not additions:
                raise AssertionError("rank fixture source rows missing")
            rows.extend(additions)
            rows.sort(key=lambda row: (
                row["operator_id"], 0 if row["record_kind"] == "summary" else 1,
                -1 if row["pivot_step"] == "NA" else int(row["pivot_step"]),
            ))
            write_csv(bundle / "rank_status.csv", fields, rows)

        def add_stray_pair_gauge(bundle: Path) -> None:
            fields, rows = read_csv(bundle / "grid_gauge.csv")
            source_id = "base.filament.r205.original.A.p037_011_029.S"
            source = next(row for row in rows if row["operator_id"] == source_id)
            addition = dict(source)
            addition.update({
                "operator_id": "base.filament.r205.original.A.p000.S",
                "sampling_operator_id": "base.filament.r205.original.A.p000.S",
                "derivative_operator_id": "base.filament.r205.original.A.p000.D",
            })
            rows.append(addition)
            rows.sort(key=lambda row: (row["operator_id"], int(row["mode_index"])))
            write_csv(bundle / "grid_gauge.csv", fields, rows)

        def add_stray_pair_null(bundle: Path) -> None:
            fields, rows = read_csv(bundle / "nullspace_modes.csv")
            source_id = "base.filament.r205.original.A.p037_011_029.S"
            source = next(row for row in rows if row["operator_id"] == source_id)
            addition = dict(source)
            addition["operator_id"] = "base.filament.r205.original.A.p000.S"
            rows.append(addition)
            rows.sort(key=lambda row: (
                row["operator_id"], row["basis_kind"], int(row["mode_index"]),
                int(row["dof_index"]),
            ))
            write_csv(bundle / "nullspace_modes.csv", fields, rows)

        reject_pair_fixture(
            "sampling-failure-stray-rank", "sampling", add_stray_pair_rank
        )
        reject_pair_fixture(
            "derivative-failure-stray-gauge", "derivative", add_stray_pair_gauge
        )
        reject_pair_fixture(
            "partial-pair-stray-null", "sampling", add_stray_pair_null
        )

        reject(
            "stale-integrity",
            lambda bundle: (bundle / "packets.csv").write_text("stale\n", encoding="utf-8"),
            refresh=False,
        )

        def packet_semantic(bundle: Path) -> None:
            mutate_csv(bundle, "packets.csv", lambda rows: rows[1].__setitem__("x_m", hx(1.25)))
            refresh_group_digest(module, bundle, "packets.csv", "base.filament.r205.original")

        reject("packet-semantic", packet_semantic)

        def neighbor_semantic(bundle: Path) -> None:
            mutate_csv(bundle, "neighbor_pairs.csv", lambda rows: rows[0].__setitem__("weight", hx(0.5)))
            refresh_group_digest(module, bundle, "neighbor_pairs.csv", "base.filament.r205.original")

        reject("neighbor-semantic", neighbor_semantic)

        def relation_semantic(bundle: Path) -> None:
            mutate_csv(bundle, "relations.csv", lambda rows: rows[0].__setitem__("reference_value", hx(2)))
            refresh_group_digest(module, bundle, "relations.csv", "base.filament.r205.original")

        reject("relation-semantic", relation_semantic)

        def operator_semantic(bundle: Path) -> None:
            mutate_csv(bundle, "operator_entries.csv", lambda rows: rows[0].__setitem__("value", hx(-0.5)))
            _fields, rows = read_csv(bundle / "operator_entries.csv")
            refresh_operator_digest(module, bundle, rows[0]["operator_id"])

        reject("operator-semantic", operator_semantic)

        def disable_built_normalization(bundle: Path, candidate: str) -> None:
            def change(rows: list[dict[str, str]]) -> None:
                row = next(item for item in rows if item["candidate"] == candidate
                           and item["build_status"] == "built")
                row["row_normalization_complete"] = "false"
                row["first_invalid_row"] = "0"
            mutate_csv(bundle, "operator_status.csv", change)

        reject(
            "built-c-normalization-false",
            lambda bundle: disable_built_normalization(bundle, "C"),
        )

        # The exact registered smoke intentionally contains no successfully
        # built B.  Exercise the same fail-closed normalization contract at the
        # operator stage using the independent four-packet unit construction;
        # it is not presented as a smoke evidence bundle.
        built_b_unit = root_path / "built-b-normalization-unit"
        make_bundle(module, built_b_unit, operator_unit_only=True)
        disable_built_normalization(built_b_unit, "B")
        unit_table_names = (
            "configurations.csv", "packets.csv", "relations.csv",
            "operator_status.csv", "operator_entries.csv",
            "moment_diagnostics.csv", "grid_nodes.csv",
        )
        unit_tables = {
            name: module.read_csv(built_b_unit / name, module.CSV_SCHEMAS[name])
            for name in unit_table_names
        }
        unit_configurations = module.validate_configuration_rows(
            unit_tables["configurations.csv"]
        )
        unit_packets, unit_positions, _unit_positions_q = module.validate_packet_tables(
            unit_tables["configurations.csv"], unit_tables["packets.csv"]
        )
        _unit_topology = module.validate_relations(
            unit_tables["configurations.csv"], unit_tables["relations.csv"],
            unit_positions, _unit_positions_q,
        )
        try:
            module.validate_operator_tables(
                unit_tables["configurations.csv"], set(unit_configurations),
                unit_packets, unit_positions, unit_tables["relations.csv"],
                unit_tables["operator_status.csv"], unit_tables["operator_entries.csv"],
                unit_tables["moment_diagnostics.csv"], unit_tables["grid_nodes.csv"],
            )
        except module.InvalidBundle:
            pass
        else:
            raise AssertionError("built B incomplete row normalization was accepted")
        mutations += 1

        reject(
            "frozen-flexibility-steering",
            lambda bundle: mutate_csv(
                bundle, "configurations.csv",
                lambda rows: (
                    rows[0].__setitem__("intentionally_flexible", "false"),
                    rows[0].__setitem__("generic_solid_gate", "true"),
                ),
            ),
        )

        reject(
            "noncanonical-integer",
            lambda bundle: mutate_csv(
                bundle, "rank_status.csv",
                lambda rows: next(row for row in rows if row["record_kind"] == "pivot")
                .__setitem__("pivot_step", "00"),
            ),
        )
        reject(
            "exact-rank",
            lambda bundle: mutate_csv(
                bundle, "exact_reference.csv", lambda rows: rows[0].__setitem__("rank", "5")
            ),
        )
        reject(
            "moment-condition",
            lambda bundle: mutate_csv(
                bundle, "moment_diagnostics.csv",
                lambda rows: rows[0].__setitem__("condition_number", hx(99)),
            ),
        )

        def qrcp_trace(bundle: Path) -> None:
            def corrupt(rows: list[dict[str, str]]) -> None:
                pivots = [row for row in rows
                          if row["operator_id"] == "base.filament.r205.original.C"
                          and row["record_kind"] == "pivot"]
                pivots[0]["diagonal_magnitude"] = hx(
                    float.fromhex(pivots[0]["diagonal_magnitude"]) * 0.5
                )
            mutate_csv(bundle, "rank_status.csv", corrupt)

        reject("qrcp-trace", qrcp_trace)

        exact_edge_mutations = {
            "exact.tetrahedron_k4_minus_edge": (
                (1, 2), (1, 3), (1, 4), (2, 3), (3, 4),
            ),
            "exact.octahedron_graph": tuple(
                edge if index else (1, 2)
                for index, edge in enumerate(module.FROZEN_EXACT_EDGES["exact.octahedron_graph"])
            ),
            "exact.cube_edge_graph": tuple(
                edge if index else (1, 4)
                for index, edge in enumerate(module.FROZEN_EXACT_EDGES["exact.cube_edge_graph"])
            ),
        }
        for configuration_id, altered in exact_edge_mutations.items():
            try:
                module.validate_frozen_exact_edge_inventory(
                    configuration_id, altered, []
                )
            except module.InvalidBundle:
                pass
            else:
                raise AssertionError(
                    f"{configuration_id} alternate exact edge graph was accepted"
                )
            mutations += 1

        try:
            module.decimal_householder_qrcp_trace(
                [[Decimal("1e-8"), Decimal(0)], [Decimal(0), Decimal("2e-8")]],
                claimed_permutation=[0, 1],
            )
        except module.InvalidBundle:
            pass
        else:
            raise AssertionError("relative QRCP pivot gate accepted a nonmaximal tiny pivot")
        mutations += 1

        try:
            module.decimal_householder_qrcp_trace(
                [[Decimal(1), Decimal(0), Decimal(0)], [Decimal(0), Decimal(0), Decimal(0)]],
                claimed_permutation=[0, 2, 1],
            )
        except module.InvalidBundle:
            pass
        else:
            raise AssertionError("QRCP replay accepted a permuted structural-zero suffix")
        mutations += 1

        def aggregate_rank(bundle: Path) -> None:
            def change(rows: list[dict[str, str]]) -> None:
                for row in rows:
                    if row["operator_id"] == "base.filament.r205.original.C":
                        row["normalized_null_residual"] = hx(1e-8)
            mutate_csv(bundle, "rank_status.csv", change)

        reject("rank-aggregate", aggregate_rank)

        def false_basis_construction_failure(bundle: Path) -> None:
            operator_id = "exact.planar_square_plus_diagonal_and_volume.D"
            rank_fields, rank_rows = read_csv(bundle / "rank_status.csv")
            for row in rank_rows:
                if row["operator_id"] != operator_id:
                    continue
                row["nonrigid_nullity"] = "NA"
                row["basis_complete"] = "false"
                for field in (
                    "rigid_in_kernel", "kernel_equals_rigid_subspace",
                    "normalized_rigid_residual", "normalized_null_residual",
                    "normalized_nonrigid_residual", "rigid_orthogonality_residual",
                    "generic_observability_pass",
                ):
                    row[field] = "NA"
                row["failure_stage"] = "basis_construction"
                row["failure_reason"] = "incomplete_kernel"
                row["status"] = "numerical_failure"
            write_csv(bundle / "rank_status.csv", rank_fields, rank_rows)
            rigid_fields, rigid_rows = read_csv(bundle / "rigid_basis.csv")
            rigid_rows = [
                row for row in rigid_rows
                if row["operator_id"] != operator_id
                or row["basis_kind"] == "raw_generator"
            ]
            write_csv(bundle / "rigid_basis.csv", rigid_fields, rigid_rows)
            for table in ("nullspace_modes.csv", "nullspace_metrics.csv"):
                fields, rows = read_csv(bundle / table)
                write_csv(
                    bundle / table,
                    fields,
                    [row for row in rows if row["operator_id"] != operator_id],
                )
            invariance_fields, invariance_rows = read_csv(bundle / "invariance.csv")
            permutation_row = next(
                row for row in invariance_rows
                if row["comparison_id"] == f"permutation.{operator_id}"
            )
            permutation_row.update({
                "rank_match": "false", "nullity_match": "false",
                "metrics_available": "false", "normalized_residual_delta": "NA",
                "max_scaled_singular_value_delta": "NA", "tolerance": "NA",
                "canonical_bytes_match": "false", "pass": "false",
            })
            write_csv(bundle / "invariance.csv", invariance_fields, invariance_rows)
            value = json.loads((bundle / "summary.json").read_text(encoding="utf-8"))
            for table in ("rigid_basis.csv", "nullspace_modes.csv", "nullspace_metrics.csv"):
                value["row_counts"][table] = len(read_csv(bundle / table)[1])
            value["invariance_all_pass"] = False
            value["decisive_rank_rows_all_unambiguous"] = False
            value["independent_reference_all_pass"] = False
            value["candidate_findings"] = {
                "A": value["candidate_findings"]["A"], "B": "inconclusive",
                "C": "inconclusive", "D": "inconclusive",
            }
            value["decision"] = "stop_inconclusive_or_implementation_failure"
            write_json(bundle / "summary.json", value)
            refresh_manifest(module, bundle)

        def candidate_a_basis_failure(bundle: Path) -> None:
            operator_id = "base.filament.r205.original.A.p037_011_029.S"
            rank_fields, rank_rows = read_csv(bundle / "rank_status.csv")
            for row in rank_rows:
                if row["operator_id"] != operator_id:
                    continue
                row["status"] = "numerical_failure"
                row["nonrigid_nullity"] = "NA"
                row["basis_complete"] = "false"
                for field in (
                    "rigid_in_kernel", "kernel_equals_rigid_subspace",
                    "normalized_rigid_residual", "normalized_null_residual",
                    "normalized_nonrigid_residual", "rigid_orthogonality_residual",
                    "generic_observability_pass",
                ):
                    row[field] = "NA"
                row["failure_stage"] = "basis_construction"
                row["failure_reason"] = "incomplete_kernel"
            write_csv(bundle / "rank_status.csv", rank_fields, rank_rows)
            for table in ("nullspace_modes.csv", "nullspace_metrics.csv"):
                fields, rows = read_csv(bundle / table)
                write_csv(
                    bundle / table, fields,
                    [row for row in rows if row["operator_id"] != operator_id],
                )
            gauge_fields, gauge_rows = read_csv(bundle / "grid_gauge.csv")
            write_csv(
                bundle / "grid_gauge.csv", gauge_fields,
                [row for row in gauge_rows if row["operator_id"] != operator_id],
            )
            value = json.loads((bundle / "summary.json").read_text(encoding="utf-8"))
            for table in (
                "nullspace_modes.csv", "nullspace_metrics.csv", "grid_gauge.csv",
            ):
                value["row_counts"][table] = len(read_csv(bundle / table)[1])
            value["negative_control_reproduced"] = False
            value["decisive_rank_rows_all_unambiguous"] = False
            value["candidate_findings"] = {
                "A": "negative_control_failed", "B": "inconclusive",
                "C": "inconclusive", "D": "inconclusive",
            }
            value["decision"] = "stop_inconclusive_or_implementation_failure"
            write_json(bundle / "summary.json", value)
            refresh_manifest(module, bundle)

        def combined_valid_negative(bundle: Path) -> None:
            rewrite_a_mode_contract_negative(module, bundle)
            rewrite_c_rank_contract_negative(module, bundle, orthogonality=True)
            false_basis_construction_failure(bundle)
            candidate_a_basis_failure(bundle)

        accept_stop(
            "combined-rank-and-basis-valid-negative",
            combined_valid_negative,
            "independent_basis_agreement",
        )
        basis_findings = json.loads(
            (root_path / "combined-rank-and-basis-valid-negative-findings.json")
            .read_text(encoding="utf-8")
        )
        if "first.independent_basis_agreement" \
                not in basis_findings["claim_mismatches"] \
                or basis_findings["derived_gates"]["producer_claims_consistent"] \
                or basis_findings["derived_gates"]["negative_control_reproduced"] \
                or basis_findings["derived_gates"][
                    "decisive_rank_rows_all_unambiguous"
                ]:
            raise AssertionError(
                "combined A/C/basis negative lost a mandatory STOP finding"
            )

        unresolved_a_controls = {
            "synthetic.A.S": {
                "available": True, "derivative_id": "synthetic.A.D",
            }
        }
        unresolved_a_ranks = {
            "synthetic.A.S": {
                "status": "numerical_failure", "ambiguous": False,
                "basis_complete": False,
            }
        }
        if module.validate_grid_gauge(
            [], {}, unresolved_a_controls, [], unresolved_a_ranks
        ):
            raise AssertionError("unresolved Candidate A produced a valid negative control")
        try:
            module.validate_grid_gauge(
                [{"operator_id": "synthetic.A.S"}], {}, unresolved_a_controls,
                [], unresolved_a_ranks,
            )
        except module.InvalidBundle:
            pass
        else:
            raise AssertionError("stray gauge row for unresolved Candidate A was accepted")
        mutations += 2

        # Exhaust the frozen Candidate-A pair contract before exercising more
        # expensive end-to-end mutations.  S is rank-applicable exactly when
        # both halves built; a successful half is retained, but a partial pair
        # admits no rank/null/gauge rows and must clear the decisive-rank gate.
        rank_states = {
            "resolved": {
                "status": "analyzed", "ambiguous": False,
                "basis_complete": True, "contract_pass": True,
                "nonrigid_nullity": 0,
                "independent_basis_agreement": True,
            },
            "ambiguous": {
                "status": "ambiguous", "ambiguous": True,
                "basis_complete": False, "contract_pass": False,
                "nonrigid_nullity": None,
                "independent_basis_agreement": True,
            },
            "numerical_failure": {
                "status": "numerical_failure", "ambiguous": False,
                "basis_complete": False, "contract_pass": False,
                "nonrigid_nullity": None,
                "independent_basis_agreement": True,
            },
        }

        def a_pair_status(s_built: bool, d_built: bool) -> dict[str, dict[str, str]]:
            pair_complete = s_built and d_built
            return {
                "synthetic.A.S": {
                    "candidate": "A",
                    "build_status": "built" if s_built else "numerical_failure",
                    "decision_driving": "true",
                    "rank_applicable": str(pair_complete).lower(),
                },
                "synthetic.A.D": {
                    "candidate": "A",
                    "build_status": "built" if d_built else "numerical_failure",
                    "decision_driving": "true", "rank_applicable": "false",
                },
            }

        pair_cases = 0
        for s_built, d_built in itertools.product((False, True), repeat=2):
            statuses = a_pair_status(s_built, d_built)
            complete = s_built and d_built
            if module.candidate_a_pair_complete("synthetic.A.S", statuses) != complete:
                raise AssertionError("Candidate-A pair-completeness table mismatch")
            if module.expected_operator_rank_applicable(
                "synthetic.A.S", statuses
            ) != complete or module.expected_operator_rank_applicable(
                "synthetic.A.D", statuses
            ):
                raise AssertionError("Candidate-A pair rank-applicability table mismatch")

            if not complete:
                # Empty evidence is the only allowed inventory.  A rank row is
                # structurally malformed even if the built half is S.
                if module.validate_rank_and_bases(
                    statuses, {}, {}, {}, [], [], [], []
                ):
                    raise AssertionError("partial A pair synthesized a rank result")
                stray_summary = {
                    "operator_id": "synthetic.A.S", "record_kind": "summary",
                    "pivot_step": "NA", "permuted_column_index": "NA",
                    "diagonal_magnitude": "NA", "accepted_pivot": "NA",
                }
                try:
                    module.validate_rank_and_bases(
                        statuses, {}, {}, {}, [stray_summary], [], [], []
                    )
                except module.InvalidBundle:
                    pass
                else:
                    raise AssertionError("partial Candidate-A pair accepted a stray rank row")
                decisive, _basis = module.derive_decisive_rank_gate(statuses, {})
                if decisive:
                    raise AssertionError("partial Candidate-A pair passed decisive-rank gate")
                pair_cases += 2
                continue

            for rank_name, rank in rank_states.items():
                ranks = {"synthetic.A.S": rank}
                expected_resolved = rank_name == "resolved"
                if module.candidate_a_rank_supports_gauge(rank) != expected_resolved:
                    raise AssertionError(
                        f"Candidate-A {rank_name} gauge-inventory policy mismatch"
                    )
                decisive, _basis = module.derive_decisive_rank_gate(statuses, ranks)
                if decisive != expected_resolved:
                    raise AssertionError(
                        f"Candidate-A {rank_name} decisive-rank policy mismatch"
                    )
                pair_cases += 1

        fixture_summary = {"mode": "failure_fixture"}
        for failed_suffix in ("S", "D"):
            target = f"base.filament.r205.original.A.p000.{failed_suffix}"
            partner_suffix = "D" if failed_suffix == "S" else "S"
            partner = f"base.filament.r205.original.A.p000.{partner_suffix}"
            fixture_statuses: dict[str, dict[str, str]] = {}
            for phase in ("p000", "p037_011_029"):
                for suffix in ("S", "D"):
                    operator_id = f"base.filament.r205.original.A.{phase}.{suffix}"
                    fixture_statuses[operator_id] = {
                        "candidate": "A", "build_status": "built",
                        "failure_stage": "NA", "failure_reason": "NA",
                        "failure_witness_row": "NA", "first_invalid_row": "NA",
                        "row_normalization_complete": "true",
                        "raw_exported": "true",
                        "rank_applicable": str(
                            phase != "p000" and suffix == "S"
                        ).lower(),
                    }
            fixture_statuses[target].update({
                "build_status": "numerical_failure",
                "failure_stage": "row_normalization",
                "failure_reason": "zero_row_norm",
                "failure_witness_row": "0", "first_invalid_row": "0",
                "row_normalization_complete": "false",
                "rank_applicable": "false",
            })
            fixture_statuses[partner]["rank_applicable"] = "false"
            if module.validate_failure_fixture_contract(
                fixture_summary, fixture_statuses
            ) != target:
                raise AssertionError(f"{failed_suffix}-failed fixture target was not bound")
            malformed = {
                key: dict(value) for key, value in fixture_statuses.items()
            }
            malformed[partner]["rank_applicable"] = "true"
            try:
                module.validate_failure_fixture_contract(fixture_summary, malformed)
            except module.InvalidBundle:
                pass
            else:
                raise AssertionError(
                    f"{failed_suffix}-failed fixture accepted rank-applicable partner"
                )
            pair_cases += 2

        # Apply the same build/rank reducer exhaustively to packet candidates.
        # A nondecision diagnostic failure is quarantined but does not clear a
        # scientific gate; every decision-driving build/rank failure does.
        packet_cases = 0
        for candidate in ("B", "C", "D"):
            for built, decision_driving in (
                (True, True), (False, True), (False, False)
            ):
                operator_id = f"synthetic.{candidate}"
                status = {
                    operator_id: {
                        "candidate": candidate,
                        "build_status": "built" if built else (
                            "not_triggered" if candidate == "D" else "numerical_failure"
                        ),
                        "decision_driving": str(decision_driving).lower(),
                        "rank_applicable": str(built).lower(),
                    }
                }
                if module.expected_operator_rank_applicable(operator_id, status) != built:
                    raise AssertionError(f"{candidate}: build/rank inventory mismatch")
                if not built:
                    if module.validate_rank_and_bases(
                        status, {}, {}, {}, [], [], [], []
                    ):
                        raise AssertionError(f"{candidate}: unbuilt operator synthesized rank")
                    stray_summary = {
                        "operator_id": operator_id, "record_kind": "summary",
                        "pivot_step": "NA", "permuted_column_index": "NA",
                        "diagonal_magnitude": "NA", "accepted_pivot": "NA",
                    }
                    try:
                        module.validate_rank_and_bases(
                            status, {}, {}, {}, [stray_summary], [], [], []
                        )
                    except module.InvalidBundle:
                        pass
                    else:
                        raise AssertionError(
                            f"{candidate}: unbuilt operator accepted stray rank row"
                        )
                    packet_cases += 2
                rank_variants = rank_states.items() if built else (("absent", None),)
                for rank_name, rank in rank_variants:
                    ranks = {} if rank is None else {operator_id: rank}
                    decisive, _basis = module.derive_decisive_rank_gate(status, ranks)
                    expected = (
                        not decision_driving
                        or (built and rank_name == "resolved")
                    )
                    if decisive != expected:
                        raise AssertionError(
                            f"{candidate}/{built}/{decision_driving}/{rank_name}: "
                            "decisive-rank table mismatch"
                        )
                    packet_cases += 1
        mutations += pair_cases + packet_cases

        for candidate in ("A", "B", "C", "D"):
            module.validate_rank_status_wire(
                f"synthetic.{candidate}", "numerical_failure",
                "basis_construction", False,
            )
            try:
                module.validate_rank_status_wire(
                    f"synthetic.{candidate}", "analyzed",
                    "basis_construction", False,
                )
            except module.InvalidBundle:
                pass
            else:
                raise AssertionError(
                    f"{candidate}: analyzed+basis-failure status was accepted"
                )
        mutations += 4

        def malformed_basis_failure_trace(bundle: Path) -> None:
            false_basis_construction_failure(bundle)
            fields, rows = read_csv(bundle / "rank_status.csv")
            pivot = next(
                row for row in rows
                if row["operator_id"]
                == "exact.planar_square_plus_diagonal_and_volume.D"
                and row["record_kind"] == "pivot"
            )
            pivot["permuted_column_index"] = "999"
            write_csv(bundle / "rank_status.csv", fields, rows)

        reject("malformed-basis-failure-trace", malformed_basis_failure_trace)

        reject(
            "rigid-basis",
            lambda bundle: mutate_csv(
                bundle, "rigid_basis.csv",
                lambda rows: next(row for row in rows if row["basis_kind"] == "raw_generator")
                .__setitem__("value", hx(0.123)),
            ),
        )

        reject(
            "finite-value",
            lambda bundle: mutate_csv(
                bundle, "affine_objectivity.csv",
                lambda rows: next(row for row in rows if row["test_kind"] == "finite_bond_length")
                .__setitem__("measured_value", hx(0.75)),
            ),
        )

        reject(
            "invariance-singular",
            lambda bundle: mutate_csv(
                bundle, "invariance.csv",
                lambda rows: rows[0].__setitem__("max_scaled_singular_value_delta", hx(5e-11)),
            ),
        )

        reject(
            "decision-hiding",
            lambda bundle: mutate_csv(
                bundle, "operator_status.csv",
                lambda rows: next(row for row in rows if row["candidate"] == "C")
                .__setitem__("decision_driving", "false"),
            ),
        )

        def operator_inventory(bundle: Path) -> None:
            fields, rows = read_csv(bundle / "operator_status.csv")
            rows = [row for row in rows if row["candidate"] != "D"]
            write_csv(bundle / "operator_status.csv", fields, rows)
            value = json.loads((bundle / "summary.json").read_text(encoding="utf-8"))
            value["registered_operator_ids"] = [row["operator_id"] for row in rows]
            value["row_counts"]["operator_status.csv"] = len(rows)
            write_json(bundle / "summary.json", value)

        reject("operator-inventory", operator_inventory)

        def stray_a_grid_node(bundle: Path) -> None:
            fields, rows = read_csv(bundle / "grid_nodes.csv")
            rows.append(dict(zip(module.GRID_NODE_FIELDS, (
                "exact.tetrahedron_k4.A.p000.S", "exact.tetrahedron_k4.A.p000.D",
                "exact.tetrahedron_k4", "p000", "0", "1", "0", "0", "0",
                hx(0), hx(0), hx(0),
            ), strict=True)))
            write_csv(bundle / "grid_nodes.csv", fields, rows)
            value = json.loads((bundle / "summary.json").read_text(encoding="utf-8"))
            value["row_counts"]["grid_nodes.csv"] = 1
            write_json(bundle / "summary.json", value)

        reject("stray-candidate-a-node", stray_a_grid_node)

        reject(
            "permutation-canonical-claim",
            lambda bundle: mutate_csv(
                bundle, "invariance.csv",
                lambda rows: next(row for row in rows
                                  if row["transform_kind"] == "packet_permutation")
                .__setitem__("canonical_bytes_match", "false"),
            ),
        )

        reject(
            "permutation-order-metadata",
            lambda bundle: mutate_csv(
                bundle, "permutation_controls.csv",
                lambda rows: rows[0].__setitem__("packet_order", "1:2:3:4"),
            ),
        )

        def hidden_rank_lifting_cell(bundle: Path) -> None:
            fields, rows = read_csv(bundle / "operator_entries.csv")
            operator_id = "exact.planar_square_plus_diagonal_and_volume.C"
            rows.append(dict(zip(module.OPERATOR_ENTRY_FIELDS, (
                operator_id, "0", "6", "packet", "3", "x", "bond_length_rate",
                "bond.1.2", "length", hx(1e-12), "one",
            ), strict=True)))
            rows.sort(key=lambda row: (
                row["operator_id"], int(row["row_index"]), int(row["column_index"])
            ))
            write_csv(bundle / "operator_entries.csv", fields, rows)
            refresh_operator_digest(module, bundle, operator_id)

        reject("hidden-structural-rank-lift", hidden_rank_lifting_cell)

        def candidate_a_rebuild(bundle: Path) -> None:
            operator_id = "base.filament.r205.original.A.p000.S"
            mutate_csv(
                bundle, "operator_entries.csv",
                lambda rows: next(row for row in rows if row["operator_id"] == operator_id)
                .__setitem__("value", hx(0.125)),
            )
            refresh_operator_digest(module, bundle, operator_id)

        reject_branch("candidate-a-sampling-rebuild", candidate_a_rebuild)

        def scale_candidate_a_mode(bundle: Path, scale: float) -> None:
            operator_id = "base.filament.r205.original.A.p000.S"
            mode_index = "0"
            def scale_rows(rows: list[dict[str, str]]) -> None:
                for row in rows:
                    if row["operator_id"] == operator_id \
                            and row["basis_kind"] == "sampling_null" \
                            and row["mode_index"] == mode_index:
                        row["value"] = hx(float.fromhex(row["value"]) * scale)
            mutate_csv(bundle, "nullspace_modes.csv", scale_rows)

            def scale_metric(rows: list[dict[str, str]]) -> None:
                row = next(item for item in rows if item["operator_id"] == operator_id
                           and item["basis_kind"] == "sampling_null"
                           and item["mode_index"] == mode_index)
                for field in ("operator_image_l2", "operator_denominator"):
                    row[field] = hx(float.fromhex(row[field]) * abs(scale))
            mutate_csv(bundle, "nullspace_metrics.csv", scale_metric)

            def scale_gauge(rows: list[dict[str, str]]) -> None:
                row = next(item for item in rows if item["operator_id"] == operator_id
                           and item["mode_index"] == mode_index)
                for field in (
                    "derivative_max_per_s", "derivative_rms_per_s",
                    "derivative_roundoff_bound_per_s",
                ):
                    row[field] = hx(float.fromhex(row[field]) * abs(scale))
                visible = float.fromhex(row["derivative_max_per_s"]) > max(
                    1e-10, 1e4 * float.fromhex(row["derivative_roundoff_bound_per_s"])
                )
                row["gradient_visible"] = str(visible).lower()
                row["pass"] = str(visible and row["accepted"] == "true").lower()
            mutate_csv(bundle, "grid_gauge.csv", scale_gauge)

        reject_branch(
            "candidate-a-basis-scale-double",
            lambda bundle: scale_candidate_a_mode(bundle, 2.0),
        )
        reject_branch(
            "candidate-a-basis-scale-tiny",
            lambda bundle: scale_candidate_a_mode(bundle, 1e-20),
        )
        canonical_basis = [
            [Decimal(1), Decimal(0)],
            [Decimal(0), Decimal(1)],
        ]
        inverse_sqrt_two = Decimal(1) / Decimal(2).sqrt()
        rotated_basis = [
            [inverse_sqrt_two, inverse_sqrt_two],
            [inverse_sqrt_two, -inverse_sqrt_two],
        ]
        derivative_control = [
            [Decimal(3), Decimal(0)],
            [Decimal(0), Decimal(1)],
        ]
        canonical_norm = module.restricted_operator_norm(
            derivative_control, canonical_basis
        )
        rotated_norm = module.restricted_operator_norm(
            derivative_control, rotated_basis
        )
        if abs(canonical_norm - rotated_norm) > Decimal("1e-12"):
            raise AssertionError("D|ker(S) norm changed under orthogonal basis mixing")
        changed_norm = module.restricted_operator_norm(
            [[Decimal(0), Decimal(0)], [Decimal(0), Decimal(0)]], rotated_basis
        )
        if not canonical_norm > Decimal(0) or changed_norm != 0:
            raise AssertionError("true D|ker(S) change was not independently resolved")
        mutations += 1

        def enriched_volume_rebuild(bundle: Path) -> None:
            operator_id = "exact.planar_square_plus_diagonal_and_volume.D"
            mutate_csv(
                bundle, "operator_entries.csv",
                lambda rows: next(
                    row for row in rows
                    if row["operator_id"] == operator_id and row["row_kind"] == "oriented_volume_rate"
                ).__setitem__("value", hx(0.5)),
            )
            refresh_operator_digest(module, bundle, operator_id)

        reject_branch("built-d-volume-rebuild", enriched_volume_rebuild)

        def alternate_planar_diagonal(bundle: Path) -> None:
            configuration_id = "exact.planar_square_plus_diagonal_and_volume"
            def change(rows: list[dict[str, str]]) -> None:
                row = next(item for item in rows if item["configuration_id"] == configuration_id
                           and item["relation_id"] == "bond.1.3")
                row["relation_id"] = "bond.2.4"
                row["first_id"] = "2"
                row["second_id"] = "4"
            mutate_csv(bundle, "relations.csv", change)
            refresh_group_digest(module, bundle, "relations.csv", configuration_id)

        reject_branch("exact-planar-diagonal-swap", alternate_planar_diagonal)

        reject_branch(
            "nonrigid-quotient-basis",
            lambda bundle: mutate_csv(
                bundle, "nullspace_modes.csv",
                lambda rows: next(
                    row for row in rows
                    if row["operator_id"] == "exact.planar_square_plus_diagonal_and_volume.C"
                    and row["basis_kind"] == "nonrigid"
                ).__setitem__("value", hx(0.25)),
            ),
        )
        reject_branch(
            "nullspace-metric-pass-steering",
            lambda bundle: mutate_csv(
                bundle, "nullspace_metrics.csv",
                lambda rows: next(
                    row for row in rows
                    if row["operator_id"] == "exact.planar_square_plus_diagonal_and_volume.C"
                    and row["basis_kind"] == "nonrigid"
                ).__setitem__("pass", "false"),
            ),
        )

        reject_branch(
            "metamorphic-resolved-spectrum",
            lambda bundle: mutate_csv(
                bundle, "invariance.csv",
                lambda rows: next(
                    row for row in rows
                    if row["comparison_id"]
                    == "metamorphic.base.filament.r205.original.translation.C"
                ).__setitem__("max_scaled_singular_value_delta", hx(1e-5)),
            ),
        )

        def metamorphic_tail_rank(bundle: Path) -> None:
            def change(rows: list[dict[str, str]]) -> None:
                for row in rows:
                    if row["operator_id"] == "base.filament.r205.original.translation.C":
                        row["rank"] = "8"
                        row["nullity"] = "16"
                        row["nonrigid_nullity"] = "11"
            mutate_csv(bundle, "rank_status.csv", change)

        reject_branch("metamorphic-rank-tail", metamorphic_tail_rank)

        cubic_positions = {
            index + 1: (module.Q(x), module.Q(y), module.Q(z))
            for index, (x, y, z) in enumerate(itertools.product(range(3), repeat=3))
        }
        cubic_ids = {
            point: packet_id for packet_id, point in cubic_positions.items()
        }
        cubic_edges = []
        for point, packet_id in cubic_ids.items():
            for axis in range(3):
                neighbor = list(point)
                neighbor[axis] += 1
                neighbor_id = cubic_ids.get(tuple(neighbor))
                if neighbor_id is not None:
                    cubic_edges.append((packet_id, neighbor_id))
        low_radius_facts = module.derive_generic_solid_facts(
            cubic_positions, cubic_edges, False
        )
        if low_radius_facts["edge_count"] != 54 \
                or low_radius_facts["edge_lower_bound"] != 75 \
                or low_radius_facts["generic_solid_gate"]:
            raise AssertionError("low-radius cubic topology was misclassified as generic")
        mutations += 1

        tetra_positions = {
            1: (module.Q(0), module.Q(0), module.Q(0)),
            2: (module.Q(1), module.Q(0), module.Q(0)),
            3: (module.Q(0), module.Q(1), module.Q(0)),
            4: (module.Q(0), module.Q(0), module.Q(1)),
        }
        complete_tetra = list(itertools.combinations(sorted(tetra_positions), 2))
        deleted_tetra = complete_tetra[:-1]
        complete_facts = module.derive_generic_solid_facts(
            tetra_positions, complete_tetra, False
        )
        deleted_facts = module.derive_generic_solid_facts(
            tetra_positions, deleted_tetra, False
        )
        if not complete_facts["generic_solid_gate"] \
                or deleted_facts["generic_solid_gate"]:
            raise AssertionError("exact deletion topology gate was not independently derived")
        mutations += 1

        def noncanonical_a_row_owner(bundle: Path) -> None:
            operator_id = "base.filament.r205.original.A.p000.S"
            mutate_csv(
                bundle, "operator_entries.csv",
                lambda rows: next(row for row in rows if row["operator_id"] == operator_id)
                .__setitem__("row_owner_id", "01"),
            )
            refresh_operator_digest(module, bundle, operator_id)

        reject_branch("noncanonical-a-row-owner", noncanonical_a_row_owner)

        def noncanonical_permuted_b_row_owner(bundle: Path) -> None:
            operator_id = "base.filament.r205.original.C"
            control_id = f"permutation.{operator_id}"
            _fields, baseline = read_csv(bundle / "operator_entries.csv")
            target = next(row for row in baseline if row["operator_id"] == operator_id)
            row_index, column_index = target["row_index"], target["column_index"]
            mutate_csv(
                bundle, "operator_entries.csv",
                lambda rows: next(
                    row for row in rows if row["operator_id"] == operator_id
                    and row["row_index"] == row_index
                    and row["column_index"] == column_index
                ).__setitem__("row_owner_id", "01"),
            )
            mutate_csv(
                bundle, "permutation_entries.csv",
                lambda rows: next(
                    row for row in rows if row["control_id"] == control_id
                    and row["row_index"] == row_index
                    and row["column_index"] == column_index
                ).__setitem__("row_owner_id", "01"),
            )
            refresh_operator_digest(module, bundle, operator_id)
            refresh_permutation_digest(module, bundle, control_id)

        reject_branch("noncanonical-permuted-b-row-owner", noncanonical_permuted_b_row_owner)

        def oversized_status(bundle: Path, operator_id: str) -> None:
            mutate_csv(
                bundle, "operator_status.csv",
                lambda rows: next(row for row in rows if row["operator_id"] == operator_id)
                .__setitem__("row_count", "1000000000000"),
            )

        reject(
            "oversized-b-dimension",
            lambda bundle: oversized_status(bundle, "base.filament.r205.original.B"),
        )
        reject(
            "oversized-c-dimension",
            lambda bundle: oversized_status(bundle, "base.filament.r205.original.C"),
        )
        reject(
            "oversized-d-dimension",
            lambda bundle: oversized_status(
                bundle, "exact.planar_square_plus_diagonal_and_volume.D"
            ),
        )
        reject_branch(
            "oversized-a-dimension",
            lambda bundle: oversized_status(
                bundle, "base.filament.r205.original.A.p000.S"
            ),
        )

        def checkpoint_trailing_byte(bundle: Path) -> None:
            fields, rows = read_csv(bundle / "checkpoints.csv")
            row = rows[0]
            payload = bytes.fromhex(row["payload_hex"]) + b"\x00"
            digest = hashlib.sha256(payload).hexdigest()
            row["payload_hex"] = payload.hex()
            row["payload_sha256"] = digest
            row["byte_count"] = str(len(payload))
            write_csv(bundle / "checkpoints.csv", fields, rows)
            config_fields, configs = read_csv(bundle / "configurations.csv")
            configs[0]["input_checkpoint_sha256_before"] = digest
            configs[0]["input_checkpoint_sha256_after"] = digest
            write_csv(bundle / "configurations.csv", config_fields, configs)

        reject("checkpoint-trailing-byte", checkpoint_trailing_byte)

        reject(
            "exact-binding",
            lambda bundle: mutate_csv(
                bundle, "exact_reference.csv",
                lambda rows: rows[0].__setitem__("operator_id", "exact.tetrahedron_k4.B"),
            ),
        )

        def noncanonical_crlf(bundle: Path) -> None:
            path = bundle / "relations.csv"
            path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))

        reject("noncanonical-crlf", noncanonical_crlf)
        reject(
            "row-order",
            lambda bundle: mutate_csv(bundle, "packets.csv", lambda rows: rows.reverse()),
        )

        def summary_decision(bundle: Path) -> None:
            value = json.loads((bundle / "summary.json").read_text(encoding="utf-8"))
            value["decision"] = "retain_central_relational_representation_for_research"
            write_json(bundle / "summary.json", value)

        def summary_promotion(bundle: Path) -> None:
            value = json.loads((bundle / "summary.json").read_text(encoding="utf-8"))
            value["promotion"] = True
            write_json(bundle / "summary.json", value)

        reject("summary-promotion", summary_promotion)

        def summary_key_order(bundle: Path) -> None:
            value = json.loads((bundle / "summary.json").read_text(encoding="utf-8"))
            reordered = {key: value[key] for key in reversed(value)}
            write_json(bundle / "summary.json", reordered)

        reject("summary-key-order", summary_key_order)

        def manifest_key_order(bundle: Path) -> None:
            value = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
            write_json(bundle / "manifest.json", {
                key: value[key] for key in reversed(value)
            })

        reject("manifest-key-order", manifest_key_order, refresh=False)

        def header_extra(bundle: Path) -> None:
            path = bundle / "packets.csv"
            text = path.read_text(encoding="utf-8")
            first, rest = text.split("\n", 1)
            path.write_text(first + ",extra\n" + rest, encoding="utf-8")

        reject("header-extra", header_extra)

        divergent = root_path / "divergent"
        shutil.copytree(base, divergent)
        value = json.loads((divergent / "summary.json").read_text(encoding="utf-8"))
        value["decision"] = "retain_central_relational_representation_for_research"
        write_json(divergent / "summary.json", value)
        refresh_manifest(module, divergent)
        divergent_findings = root_path / "divergent-findings.json"
        comparison = run_validator(
            args.validator, base, divergent, divergent_findings
        )
        if comparison.returncode != 0:
            raise AssertionError(
                f"structurally valid nondeterminism was rejected\n{comparison.stderr}"
            )
        divergent_result = json.loads(divergent_findings.read_text(encoding="utf-8"))
        if divergent_result["comparison_status"] != "nondeterministic" \
                or divergent_result["decision"] \
                != "stop_inconclusive_or_implementation_failure" \
                or divergent_result["promotion"] \
                or [row["path"] for row in divergent_result["mismatches"]] \
                != ["manifest.json", "summary.json"] \
                or "second.decision" not in divergent_result["claim_mismatches"] \
                or "comparison.nondeterminism_detected" \
                not in divergent_result["claim_mismatches"]:
            raise AssertionError("nondeterministic comparison findings are incomplete")
        mutations += 1

        synthetic_summary = {
            "mode": "full", "nondeterminism_detected": False,
            **{field: True for field in (
                "checkpoint_round_trip_all_pass", "diagnostics_read_only_all_exact",
                "neighbor_lookup_all_agree", "affine_objectivity_all_pass",
                "finite_objectivity_all_pass", "invariance_all_pass",
                "decisive_rank_rows_all_unambiguous", "raw_decision_rows_all_exported",
                "independent_reference_all_pass",
            )},
        }
        synthetic_configuration = "base.sc3.r180.original"
        synthetic_status = {
            f"{synthetic_configuration}.B": {
                "candidate": "B", "decision_driving": "true", "rank_applicable": "true",
                "b_rank_eligible": "true", "generic_solid_gate": "true", "build_status": "built",
                "configuration_id": synthetic_configuration,
                "row_normalization_complete": "true", "raw_exported": "true",
            },
            f"{synthetic_configuration}.C": {
                "candidate": "C", "decision_driving": "true", "rank_applicable": "true",
                "b_rank_eligible": "false", "generic_solid_gate": "true", "build_status": "built",
                "configuration_id": synthetic_configuration,
                "row_normalization_complete": "true", "raw_exported": "true",
            },
            f"{synthetic_configuration}.D": {
                "candidate": "D", "decision_driving": "true", "rank_applicable": "true",
                "b_rank_eligible": "false", "generic_solid_gate": "true", "build_status": "built",
                "configuration_id": synthetic_configuration,
                "row_normalization_complete": "true", "raw_exported": "true",
            },
        }
        synthetic_ranks = {
            f"{synthetic_configuration}.B": {"status": "analyzed", "ambiguous": False, "basis_complete": True,
                    "contract_pass": True, "generic_pass": False, "nonrigid_nullity": 1},
            f"{synthetic_configuration}.C": {"status": "analyzed", "ambiguous": False, "basis_complete": True,
                    "contract_pass": True, "generic_pass": False, "nonrigid_nullity": 1},
        }
        findings, decision = module.derive_decision(
            synthetic_summary, synthetic_status, synthetic_ranks, True,
            {synthetic_configuration},
        )
        if decision != "stop_inconclusive_or_implementation_failure" \
                or findings["D"] != "inconclusive":
            raise AssertionError("triggered D missing rank became a scientific failure")
        mutations += 1

        generic_b_failure_status = {
            key: dict(value) for key, value in synthetic_status.items()
        }
        generic_b_failure_status[f"{synthetic_configuration}.B"].update({
            "build_status": "numerical_failure", "rank_applicable": "false",
            "b_rank_eligible": "false", "row_normalization_complete": "false",
            "raw_exported": "false",
        })
        generic_b_failure_ranks = {
            key: value for key, value in synthetic_ranks.items()
            if not key.endswith(".B")
        }
        generic_b_failure_summary = dict(synthetic_summary)
        generic_b_failure_summary["decisive_rank_rows_all_unambiguous"] = False
        generic_b_failure_summary["raw_decision_rows_all_exported"] = False
        findings, decision = module.derive_decision(
            generic_b_failure_summary, generic_b_failure_status,
            generic_b_failure_ranks, True, {synthetic_configuration},
        )
        if decision != "stop_inconclusive_or_implementation_failure" \
                or findings["B"] != "inconclusive":
            raise AssertionError("valid generic B implementation failure escaped STOP")
        mutations += 1

        rigid_c_ranks = {
            f"{synthetic_configuration}.B": {
                "status": "analyzed", "ambiguous": False,
                "basis_complete": True, "contract_pass": True,
                "generic_pass": True, "nonrigid_nullity": 0,
            },
            f"{synthetic_configuration}.C": {
                "status": "analyzed", "ambiguous": False,
                "basis_complete": True, "contract_pass": True,
                "generic_pass": True, "nonrigid_nullity": 0,
            },
            f"{synthetic_configuration}.D": {
                "status": "analyzed", "ambiguous": False,
                "basis_complete": True, "contract_pass": True,
                "generic_pass": True, "nonrigid_nullity": 0,
            },
        }
        findings, decision = module.derive_decision(
            synthetic_summary, synthetic_status, rigid_c_ranks, True,
            {synthetic_configuration},
        )
        if decision != "stop_inconclusive_or_implementation_failure" \
                or findings["D"] != "inconclusive":
            raise AssertionError("unexpected generic D without C failure was accepted")
        mutations += 1

        second_configuration = "base.bcc35.r180.original"
        d_status = {
            f"{synthetic_configuration}.C": {
                "candidate": "C", "configuration_id": synthetic_configuration,
                "build_status": "built", "row_normalization_complete": "true",
                "raw_exported": "true",
            },
            f"{synthetic_configuration}.D": {
                "candidate": "D", "configuration_id": synthetic_configuration,
                "build_status": "built", "row_normalization_complete": "true",
                "raw_exported": "true",
            },
            f"{second_configuration}.C": {
                "candidate": "C", "configuration_id": second_configuration,
                "build_status": "built", "row_normalization_complete": "true",
                "raw_exported": "true",
            },
            f"{second_configuration}.D": {
                "candidate": "D", "configuration_id": second_configuration,
                "build_status": "not_triggered", "row_normalization_complete": "false",
                "raw_exported": "false",
            },
        }
        d_ranks = {
            f"{synthetic_configuration}.C": {
                "status": "analyzed", "ambiguous": False,
                "basis_complete": True, "contract_pass": True,
                "generic_pass": False, "nonrigid_nullity": 1,
            },
            f"{second_configuration}.C": {
                "status": "analyzed", "ambiguous": False,
                "basis_complete": True, "contract_pass": True,
                "generic_pass": True, "nonrigid_nullity": 0,
            },
        }
        first_tuple = (1, 2, 3, 4)
        second_tuple = (5, 6, 7, 8)
        d_topology = {
            synthetic_configuration: {
                "volumes": [first_tuple], "frozen_enrichment": [first_tuple],
            },
            second_configuration: {
                "volumes": [], "frozen_enrichment": [first_tuple],
            },
        }
        try:
            module.validate_global_d_inventory(
                d_status, d_ranks, d_topology,
                {synthetic_configuration, second_configuration},
            )
        except module.InvalidBundle:
            pass
        else:
            raise AssertionError("partial global D configuration sweep was accepted")
        mutations += 1

        d_status[f"{second_configuration}.D"]["build_status"] = "built"
        d_status[f"{second_configuration}.D"]["row_normalization_complete"] = "true"
        d_status[f"{second_configuration}.D"]["raw_exported"] = "true"
        d_topology[second_configuration]["volumes"] = [first_tuple]
        d_topology[second_configuration]["frozen_enrichment"] = [
            first_tuple, second_tuple
        ]
        try:
            module.validate_global_d_inventory(
                d_status, d_ranks, d_topology,
                {synthetic_configuration, second_configuration},
            )
        except module.InvalidBundle:
            pass
        else:
            raise AssertionError("partial global D selector tuple set was accepted")
        mutations += 1

        d_ranks[f"{synthetic_configuration}.C"]["nonrigid_nullity"] = 0
        try:
            module.validate_global_d_inventory(
                d_status, d_ranks, d_topology,
                {synthetic_configuration, second_configuration},
            )
        except module.InvalidBundle:
            pass
        else:
            raise AssertionError("unexpected global D inventory without trigger was accepted")
        mutations += 1

        no_d_status = {
            key: dict(value) for key, value in synthetic_status.items()
        }
        no_d_status[f"{synthetic_configuration}.D"].update({
            "build_status": "not_triggered", "decision_driving": "false",
            "rank_applicable": "false", "row_normalization_complete": "false",
            "raw_exported": "false",
        })
        no_d_ranks = {
            key: value for key, value in rigid_c_ranks.items()
            if not key.endswith(".D")
        }
        affine_failed_summary = dict(synthetic_summary)
        affine_failed_summary["affine_objectivity_all_pass"] = False
        findings, decision = module.derive_decision(
            affine_failed_summary, no_d_status, no_d_ranks, True,
            {synthetic_configuration},
        )
        if decision != "stop_inconclusive_or_implementation_failure" \
                or findings["B"] != "inconclusive" or findings["C"] != "inconclusive":
            raise AssertionError("mandatory full-gradient failure reached a scientific decision")
        mutations += 1

        for label in (
            "rigid_in_kernel_false", "null_residual_over_tolerance",
            "nonrigid_residual_over_tolerance", "metric_pass_false",
        ):
            untrusted_ranks = {
                key: dict(value) for key, value in no_d_ranks.items()
            }
            untrusted_ranks[f"{synthetic_configuration}.C"]["contract_pass"] = False
            findings, decision = module.derive_decision(
                synthetic_summary, no_d_status, untrusted_ranks, True,
                {synthetic_configuration},
            )
            if decision != "stop_inconclusive_or_implementation_failure" \
                    or findings["C"] != "inconclusive":
                raise AssertionError(f"{label} reached a scientific decision")
            mutations += 1

        inconsistent_classification = {
            key: dict(value) for key, value in no_d_ranks.items()
        }
        inconsistent_classification[f"{synthetic_configuration}.C"]["generic_pass"] = False
        findings, decision = module.derive_decision(
            synthetic_summary, no_d_status, inconsistent_classification, True,
            {synthetic_configuration},
        )
        if decision != "stop_inconclusive_or_implementation_failure" \
                or findings["C"] != "inconclusive":
            raise AssertionError("inconsistent generic-pass classification was accepted")
        mutations += 1

        mandatory_status = {
            "generic.B": {"decision_driving": "true"},
            "generic.C": {"decision_driving": "true"},
            "generic.D": {"decision_driving": "true"},
            "diagnostic.B": {"decision_driving": "false"},
        }
        for candidate in ("B", "C", "D"):
            unavailable_row = {
                "comparison_id": f"metamorphic.generic.{candidate}",
                "base_operator_id": f"generic.{candidate}",
                "transformed_operator_id": f"generic.{candidate}",
                "metrics_available": "false",
                "pass": "true",
            }
            if module.derive_invariance_aggregate(
                [unavailable_row], mandatory_status
            ):
                raise AssertionError(
                    f"mandatory unavailable {candidate} invariance passed aggregate"
                )
        diagnostic_row = dict(unavailable_row)
        diagnostic_row.update({
            "comparison_id": "metamorphic.diagnostic",
            "base_operator_id": "diagnostic.B",
            "transformed_operator_id": "diagnostic.B",
        })
        if not module.derive_invariance_aggregate([diagnostic_row], mandatory_status):
            raise AssertionError("matched nondecision failure parity was rejected")
        mutations += 4

        failed_c_inventory = module.expected_invariance_inventory(
            {"failed.C": {
                "candidate": "C", "build_status": "numerical_failure",
            }},
            {"failed": {
                "variant": "original", "base_configuration_id": "failed",
                "geometry_scale": hx(1), "transform": "identity",
            }},
        )
        if failed_c_inventory != {
            "lookup_phase.failed": (
                "failed.C", "failed.C", "lookup_phase", Decimal(1),
                "p000_to_p037_011_029",
            )
        }:
            raise AssertionError("attempted failed C lost mandatory lookup inventory")
        mutations += 1

        trigger_status = {
            "generic.one.C": {
                "candidate": "C", "configuration_id": "generic.one",
                "build_status": "built", "row_normalization_complete": "true",
                "raw_exported": "true",
            },
            "generic.two.C": {
                "candidate": "C", "configuration_id": "generic.two",
                "build_status": "built", "row_normalization_complete": "true",
                "raw_exported": "true",
            },
        }
        trigger_ranks = {
            "generic.one.C": {
                "status": "analyzed", "ambiguous": False,
                "basis_complete": True, "contract_pass": True,
                "nonrigid_nullity": 1,
            },
            "generic.two.C": {
                "status": "analyzed", "ambiguous": False,
                "basis_complete": True, "contract_pass": False,
                "nonrigid_nullity": 0,
            },
        }
        if module.derive_global_d_trigger(
            trigger_status, trigger_ranks, {"generic.one", "generic.two"}
        ):
            raise AssertionError("D triggered before every generic C contract was accepted")
        trigger_ranks["generic.two.C"]["contract_pass"] = True
        if not module.derive_global_d_trigger(
            trigger_status, trigger_ranks, {"generic.one", "generic.two"}
        ):
            raise AssertionError("accepted nonrigid generic C failed to trigger D")
        mutations += 2

        findings_gates = {
            "affine_objectivity_all_pass": True,
            "checkpoint_round_trip_all_pass": True,
            "decisive_rank_rows_all_unambiguous": True,
            "deterministic_repeatability": True,
            "diagnostics_read_only_all_exact": True,
            "finite_objectivity_all_pass": True,
            "independent_basis_agreement": True,
            "independent_reference_all_pass": True,
            "invariance_all_pass": True,
            "negative_control_reproduced": True,
            "neighbor_lookup_all_agree": True,
            "producer_claims_consistent": True,
            "raw_decision_rows_all_exported": True,
        }
        outcome = {
            "source_sha": "a" * 40, "mode": "full",
            "nondeterminism_detected": False,
            "_validator_derived_gates": findings_gates,
            "_validator_claim_mismatches": [],
            "_validator_candidate_findings": {
                "A": "negative_control_reproduced",
                "B": "reject_averaged_single_gradient_packet_kinematics",
                "C": "retain_central_relational_representation_for_research",
                "D": "not_triggered",
            },
            "_validator_decision": "retain_central_relational_representation_for_research",
        }
        divergent_outcome = dict(outcome)
        divergent_outcome["_validator_derived_gates"] = {
            **findings_gates,
            "independent_reference_all_pass": False,
            "producer_claims_consistent": False,
        }
        divergent_outcome["_validator_claim_mismatches"] = [
            "independent_reference_all_pass", "candidate_findings", "decision"
        ]
        divergent_outcome["_validator_candidate_findings"] = {
            "A": "negative_control_reproduced", "B": "inconclusive",
            "C": "inconclusive", "D": "inconclusive",
        }
        divergent_outcome["_validator_decision"] = (
            "stop_inconclusive_or_implementation_failure"
        )
        findings = module.build_validator_findings(
            [divergent_outcome], ["b" * 64], [], "c" * 64
        )
        if findings["decision"] != "stop_inconclusive_or_implementation_failure" \
                or findings["derived_gates"]["independent_reference_all_pass"] \
                or "first.independent_reference_all_pass" \
                not in findings["claim_mismatches"]:
            raise AssertionError("independent reference mismatch escaped STOP findings")
        mismatched = module.build_validator_findings(
            [outcome, outcome], ["d" * 64, "e" * 64], [{
                "path": "summary.json", "first_sha256": "f" * 64,
                "second_sha256": "0" * 64,
            }], "c" * 64,
        )
        if mismatched["comparison_status"] != "nondeterministic" \
                or mismatched["derived_gates"]["deterministic_repeatability"] \
                or mismatched["decision"] != "stop_inconclusive_or_implementation_failure":
            raise AssertionError("nondeterministic findings did not quarantine the result")
        claimed_divergence = dict(outcome)
        claimed_divergence["nondeterminism_detected"] = True
        try:
            module.build_validator_findings(
                [claimed_divergence, claimed_divergence],
                ["d" * 64, "d" * 64], [], "c" * 64,
            )
        except module.InvalidBundle:
            pass
        else:
            raise AssertionError("claimed divergence with identical bundles was accepted")
        wrong_source = dict(outcome)
        wrong_source["source_sha"] = "9" * 40
        try:
            module.build_validator_findings(
                [outcome, wrong_source], ["d" * 64, "e" * 64], [], "c" * 64
            )
        except module.InvalidBundle:
            pass
        else:
            raise AssertionError("different-source bundles entered repeatability comparison")
        try:
            module.build_validator_findings(
                [outcome, outcome], ["d" * 64, "e" * 64], [{
                    "path": "../summary.json", "first_sha256": "f" * 64,
                    "second_sha256": "0" * 64,
                }], "c" * 64,
            )
        except module.InvalidBundle:
            pass
        else:
            raise AssertionError("malformed divergence record entered findings")
        mutations += 5

        diagonal_values, diagonal_error = module.singular_values_reference([
            [Decimal("1e-8"), Decimal(0), Decimal(0)],
            [Decimal(0), Decimal("2e-8"), Decimal(0)],
            [Decimal(0), Decimal(0), Decimal("4e-8")],
        ])
        expected_diagonal = [Decimal("4e-8"), Decimal("2e-8"), Decimal("1e-8")]
        if any(abs(actual - expected) > diagonal_error
               for actual, expected in zip(
                   diagonal_values, expected_diagonal, strict=True
               )) or diagonal_error >= Decimal("1e-20"):
            raise AssertionError("direct singular-value reference lost resolved diagonal modes")
        altered_values, _altered_error = module.singular_values_reference([
            [Decimal("1e-8"), Decimal(0), Decimal(0)],
            [Decimal(0), Decimal("2.5e-8"), Decimal(0)],
            [Decimal(0), Decimal(0), Decimal("4e-8")],
        ])
        if altered_values == diagonal_values:
            raise AssertionError("resolved singular-value change was hidden")
        mutations += 1

    print(
        "mechanical observability bundle validator regression: PASS "
        f"(1 byte-identical positive pair including A/D/nonrigid/metamorphic, "
        f"{mutations} mutations)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
