%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% ALGO to minimize slippage
% 
% The main idea is to divide an initial order in smaller pieces. We then
% create a sequence of smaller sized orders until the initial order amount
% is filled. 
%
% We then measure the change in price at a relatively high rate (or maybe even continuously via websockets) and determine
% the size of the next partial orders based on the price action (rate of change and direction). If the price is
% moving up we accelerate the buying proportional to the change (because we don't want to move too far away
% from the target price) and if the price is moving down we slow down the
% buying to try to get a better average price. This process is reversed (go
% faster if price goes down and go slower if price goes up) if we are
% selling instead of buying. 
% 
% 
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

clear

dataG=importdata('last_with_2s.csv');%data set to test 
dataG1=dataG.data;

sz1=size(dataG1);% size of data 
scan_s=2;% price scanning time in s, we scan prices at given price intervals

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% INITIALIZATION 
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
getP=1; 
if getP==1
clear Prices1
k=1;
LengG=5;%execution time in minutes, this the total execution time based on user preference 
seg1=LengG*60/scan_s; % for testing purposes we divide the data in segments (to get some stats)

for im=1:sz1(2)
    stock1=dataG1(:,im);
    Ng=floor( length(stock1)/seg1);
   for j=1:Ng
       seg2=(j-1)*seg1+1:seg1*j;
       Prices1{k}=stock1(seg2);
       k=k+1;
   end
    
end

end  %getP

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
N=LengG*60/scan_s;% number of incoming prices 
PS=1;% value of stock at rebalancing 


clear MG1
clear FillG
clear FillX
%trendS=0+0.001*randn(1);%0.007
%trend1=trendS*PS;% trend amount 
t=linspace(0,1,N); %time 
Nord=1; %number of orders rounds

%initialize variables 
b1=N;

OrdG=[];
IndG=[];
FillR=[];
pm1=1;
clear PS1
PS2=[];
clear D1
clear D2
DD1=[];
DD2=[];
lim1=0;
s1=1;
II1=[];
St1=[];

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% START OF SIMULATION 

TotOrd=1*10^4; % total order


for r1=1:k-10
    
X=Prices1{r1};

rat1=X(1)/TotOrd;

%maxT1=(X(end)-X(1))/X(1);
%maxT1=0.15;
%maxT=maxT1*abs(randn(1));
%trendS=0+maxT/max(t);%0.007   
%X=PS+PS*scatter1*randn(1,N)+t*trendS;

j1=1;
clear Ord1
clear I    
clear Fill
fill1=0;

clear orders1a
clear orders2a
clear orders3a
clear orders4a
clear indO
clear sizeO
clear SL1
clear D1
clear D2
clear STK

Ord1=[];

Fill(1)=0;
FillM=zeros(1,5);

size1=1/Nord;% size of initial chunck of orders

rem1=1-size1;
aL=100; % variable to adjust size of order, based on heuristic
aL2=10000;% variable to adjust size of order, basedon on heuristic 
remA=0;
S1=0;% weigth of order
clear check1
check1=0;

for i=1:N
    rem1=1-S1;
    
    if j1>1 && Fill(j1-1)>=rem1      %fill with remaining 
    size1a=1-Fill(j1-1);
    size1=ceil(size1a*aL2)/aL2; 
    end
    
rat1=X(1)/(size1*TotOrd);


if i>1

    delta1=( X(i-1)-X(1) )/X(1)*100; % delta1 measures in % how far we moved relative to initial price

  if delta1<0 %negative prices changes (relative to initial price) 
      
    ord1a=X(i-1);  % create order at current price 
    ord1=floor( ord1a*aL)/aL; %fragment order 
    ord2=ord1+0.01; % make order slightly bigger 
    check1=1;
    lim1=0;
    
    ParN1=0.019;% Parameter to determine rate of order size 
    expN1=0.311;% Parameter to determine rate of order size 
    denN1=1;
    S1=ParN1*abs(delta1).^expN1/denN1;% Rate of size of order formula 
    
    if delta1<-0.4 % cutoff , if price has drift far enough in negative territory fill remaining orders 
          S1=1*(1-Fill(j1-1))/size1; 
          lim1=0; 
    end
    
  elseif delta1==0  % no changes in price 
    ord1a=X(i-1);  
    ord1=floor( ord1a*aL)/aL; 
    ord2=ord1;
    
    ParZ=0.021;
    S1=ParZ;%0.12
      
  elseif delta1>0 % positive prices changes (relative to initial price) 
    %ord1=ord1;
    ord1=floor( X(i-1)*aL)/aL; % fragmenting orders 
    ord2=ord1+0.01; % adding a small % to order size
    
    %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
    
    ParP=0.008;%  Parameter to determine rate of order size 
    expP1=0.4;%  Parameter to determine rate of order size 
    denP1=0.2;% Parameter to determine rate of order size 
    S1=ParP*abs(delta1).^(expP1)/denP1;% Rate of size of order formula 
    check1=1;  
    lim1=1;
                 if delta1>0.28 % cut off
                    S1=10^-10;
                 end
    
  else % covers other cases 
    ord1=floor( X(i-1)*aL)/aL;
    ord2=ord1+0.01;       
    S1=0.1;%
 
  end

else
    
ord1=X(1);
ord2=ord1+0.001;
S1=0.08;% initial order at X(1), we make a small order at start of the cycle 
delta1=0; % initialize delta 
delta2=0;

end

orders1a(i)=ord1;   
  
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%fill fully if just before end of cycle
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
 if i==N-40 %
       size1=(1-Fill(j1-1))/S1; 
 end
 
 
 ik=i;
 %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%  
   if X(ik)<ord1
   Ord1(j1)=ord1;
   
   sizeG=ceil(S1*size1*TotOrd/X(1))*X(1)/TotOrd; % orders in shares 
   sizeO(j1)=sizeG;
   
   if sizeO(j1)<rat1
      sizeO(j1)=rat1; 
   end
   
   indO(j1)=1;
   FillM(j1)=1;
   
   fill1=fill1+sizeO(j1);
   Fill(j1)=fill1;
   I(j1)=i;
   D1(j1)=delta1;
   D2(j1)=delta2;
 
   
    if Fill(j1)>=1
      sizeO(j1)=1-Fill(j1-1);
      Fill(j1)=Fill(j1-1)+sizeO(j1); % amound filled 
    end
    
             if check1==1
                 checkF(s1)=Fill(j1);% check 
                 s1=s1+1;
             end
              
   STK(j1)=floor(sizeO(j1)*TotOrd/X(i));          
   
   j1=j1+1;
   
   elseif X(ik)==ord1
       
   Ord1(j1)=ord1;
  
  sizeG=ceil(S1*size1*TotOrd/X(1))*X(1)/TotOrd;
  sizeO(j1)=sizeG;
  
  
    if sizeO(j1)<rat1
      sizeO(j1)=rat1; 
   end
   
   
   indO(j1)=1;
   FillM(j1)=2;
   fill1=fill1+sizeO(j1);
   Fill(j1)=fill1;
   I(j1)=i;
   D1(j1)=delta1;
   D2(j1)=delta2;
   
    if Fill(j1)>=1
      sizeO(j1)=1-Fill(j1-1);
      Fill(j1)=Fill(j1-1)+sizeO(j1);
    end
   
   
             if check1==1
                 checkF(s1)=Fill(j1);
                 s1=s1+1;
             end
              
             
   STK(j1)=floor(sizeO(j1)*TotOrd/X(i));            
   j1=j1+1;    
       
   elseif X(ik)>ord1 && X(ik)<=ord2 && check1==1 && lim1==1 %stop-loss limit
     
   Ord1(j1)=ord2;
   
   sizeG=ceil(S1*size1*TotOrd/X(1))*X(1)/TotOrd;
   sizeO(j1)=sizeG;
   
    if sizeO(j1)<rat1
      sizeO(j1)=rat1; 
   end
   
   indO(j1)=1;
   FillM(j1)=3;
   fill1=fill1+sizeO(j1);
   Fill(j1)=fill1;
   if Fill(j1)>=1
      sizeO(j1)=1-Fill(j1-1);
      Fill(j1)=Fill(j1-1)+sizeO(j1);
   end
   
   I(j1)=i;
   D1(j1)=delta1;
   D2(j1)=delta2;
   
   
              if check1==1
                 checkF(s1)=Fill(j1);
                 s1=s1+1;
              end
   STK(j1)=floor(sizeO(j1)*TotOrd/X(i));  
   j1=j1+1;    
   
   end % if X 
              
   
              if j1>1 && Fill(j1-1)>=1
                b1=i;    
                break
               end   
    
    
end% for i

if length(Ord1)>=1
MG1(r1)=sum(Ord1.*sizeO)/sum(sizeO);%weighted slippage

FillG(r1)=max(Fill);
OrdG=[OrdG Ord1];
IndG=[IndG indO];

FillR=[FillR sizeO];
[Fx1,Ix1]=max(FillM); 
FillX(r1)=Fx1;
PS1(r1)=X(1);% target prices 

PS2=[PS2 X(1).*ones(1,length(Ord1))];
DD1=[DD1 D1];
DD2=[DD2 D2];

II1=[II1 I];

St1=[St1 STK];

else
   pm1=pm1+1
   
end

end % for r1

seg1a=10;
int1=floor(N/seg1a);
clear MP
clear IP
for ix=1:int1
seg2a=seg1a*(ix-1)+1:seg1a*ix;    
MP(ix)=mean(X(seg2a));    
IP(ix)=min(seg2a);    
end

PS1a=X(1);

% last example 
M1=mean(Ord1)
Slippage=(M1-PS1a)/PS1a*100 
St10=std(Ord1)
n1=j1/max(I)*100
T=N*scan_s;
tM1=max(I)*scan_s;

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

time=linspace(0,T,N);
N1=length(orders1a);
T1=N1*scan_s;
time1=linspace(0,T1,N1);

figure(100)
plot(time,X,'k.')
hold on
plot(time(I),Ord1,'r*')
plot(time,PS1a*ones(1,N),'r-')
plot(time(IP),MP,'b-')
plot(time1,orders1a,'m--')
% plot(time1,orders2a,'m--')
% plot(time1,orders3a,'m--')
% plot(time1,orders4a,'m--')
hold off
legend('Incoming Prices','Executed Orders','Target Price','mean prices','Orders Layer')
xlabel('seconds from rebalancing')
ylabel('Price $')

if Fill<1
    ind1=j1-1;
else
    ind1=j1;
end

m1=1;

%ylim([PS1-0.002*PS1 PS+0.002*PS])
% t1=['Orders Success Rate % = ' num2str(n1) ', slippage = ' num2str(Slippage) ', Price above, Price +  ' num2str(m1*100) ' %' ', Price below, Price -  ' num2str(m2*100) ' %' ', Size order below % = ' num2str(S3+S4), ', Fill= ' num2str(Fill(ind1)*100 ) ' %' ];
% t2=['Number of Orders = ' num2str(Nord), ', Trend Change in 5 min = ' num2str(maxT1*100) ' %', ', Execution Time = ' num2str(tM1) ' s'];
% t3={t1,t2};
% title(t3)


Slippage1=(OrdG-PS2)./PS2*100;% slippage not weigthed 
mR=mean(Slippage1)

figure(200)
plot(Slippage1,'k.')
hold on
plot(zeros(1,length(Slippage1)),'c-')
hold off
title(['Slippage, mean = ' num2str(mR) ])
SM1=FillR.*OrdG/sum(OrdG);

OSM2=sum(Slippage1.*FillR)/sum(FillR)

% SlipM=(FillR-PS2 )./PS2*100;
% 
% mRM=mean(SlipM);
% 
% figure(300)
% plot(SlipM,'k.')
% hold on
% plot(zeros(1,length(SlipM)),'c-')
% hold off
% title(['Weighted Slippage per trade, mean = ' num2str(mRM) ])


figure(220)
subplot(3,1,1)
plot(Slippage1,'k.')
title(['Slippage, mean = ' num2str(mR) ])
subplot(3,1,2)
plot(DD1,'k.')
subplot(3,1,3)
ylabel('Velocity')
plot(DD2,'k.')
ylabel('accel')

ratF=length(find(FillG>=0.99))/length(FillG);
figure(202)
plot(FillG,'k.')
title(['Filled Orders = ' num2str(ratF) ' % '])
%ylim([0.9 1.01])

Sl1=(MG1-PS1)./PS1*100;
MN1=mean(Sl1);



ran1=linspace(-0.01,0.01,200);
H1=histc(Sl1,ran1);

figure(201)
bar(ran1,H1/sum(H1))
xlabel('Weighted Slippage')
title(['W Slippage, mean = ' num2str(mean(Sl1)) ', median = ' num2str(median(Sl1))]) 
ylim([0 0.03])

% figure(111)
% plot(time,X,'k.')
% hold on
% % plot(time(I),Ord1,'r*')
% plot(time,PS1a*ones(1,N),'r-')
% %plot(time(IP),MP,'b-')
% plot(time1,orders1a,'m--')
% % plot(time1,orders2a,'m--')
% % plot(time1,orders3a,'m--')
% % plot(time1,orders4a,'m--')
% hold off

clear BG
for i=1:5
BG(i)=length( find(IndG==i));
end
figure(112)
plot(IndG,'k.')

figure(113)
bar(BG/sum(BG)*100)
ylabel('percent filled')
xlabel('Layers (1 is top)')

PP1=[];
PP2=[];

% for i1=1:length(Prices1)
% figure(118)
% SLG1=(Prices1{i1}-1)/1*100;
% plot(SLG1,'k.')
% PP1=[PP1 SLG1];
% PP2=[PP2 SLG1'];
% hold on
% end

% figure(119)
% plot(mean(PP1),'-')


% rang1=linspace(-0.1,0.1,100);
% H1C=histc(PP2,rang1);
% 
% figure(210)
% bar(rang1,H1C)

figure(211)
plot(FillX+0.1*randn(1,length(FillX)).*FillX,Sl1,'k.')
xlabel('Max Fill Level')
ylabel('Slippage')

F3=find(FillX==3);
M3=mean(Sl1(F3))

F2=find(FillX==2);
M2=mean(Sl1(F2))

F1=find(FillX==1);
M1=mean(Sl1(F1))

figure(213)
plot(Slippage1,DD2,'k.')

Slip1=(Ord1-X(1))/X(1)*100;% slippage

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
figure(214)
plot(Slip1,sizeO,'k.')
xlabel('Slippage')
ylabel('Size')
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
actual=OrdG;
rate=PS2;
total=FillR;
buyT=1:length(actual);
sellT=buyT;

DiffS1= actual(sellT).*total(sellT);
DiffS2=rate(sellT).*total(sellT);
DiffB1= actual(buyT).*total(buyT);
DiffB2=rate(buyT).*total(buyT);

DP2=actual(buyT)-rate(buyT);
DP1=actual(sellT)-rate(sellT);

%DiffB=( actual(buyT).*total(buyT)-rate(buyT).*total(sellT) )./(rate(buyT).*total(buyT))*1000;

figure(7)
plot(DiffS1,'k.')

D1=DiffS1-DiffS2;
D2=DiffB1-DiffB2;

figure(8)
plot(D1,'k.')

figure(9)
plot(DiffB1,'k.')

figure(10)
plot(D2,'k.')

figure(11)
plot(DP1,D1,'k.')
ylabel('total amount difference B')
xlabel('Price difference')

figure(12)
plot(DP2,D2,'k.')
ylabel('total amount difference S')
xlabel('Price difference')

TotS1=sum(rate(sellT).*total(sellT))
TotS2=sum(actual(sellT).*total(sellT))

TotB1=sum(rate(buyT).*total(buyT)*TotOrd./rate(buyT))
TotB2=sum(actual(buyT).*total(buyT)*TotOrd./rate(buyT))

DB1=TotB2-TotB1
DBP1=(TotB2-TotB1)/TotB1*100


DS1=TotS2-TotS1
DSP1=(TotS2-TotS1)/TotS1*100

Sum1=sum(total)/r1

figure(15)
plot(FillR,'k.')

figure(16)
plot(FillG,'k.')

figure(303)% main result 
plot(Sl1,'k.')
title(['Mean Weighted Slippage = ' num2str(MN1) ', Fill Rate = ' num2str(ratF), ', Mean Fill =' num2str(mean(FillG)), ', Effective Total Slippage = ' num2str(DBP1) ])

figure(305)
plot(St1,'k.')
ylabel('Stocks')


