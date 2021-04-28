%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
user=' '
password=' ' 

for J=1:2
    
    
algoA=J;
if algoA==1
    algo1=1; % OPTIMUS 1
elseif algoA==2
    algo1=2; % MINO 1
end


URL1=1;

clear token
if URL1==1
    url = 'https://alphahub.us/api/v1/';
    sessionURL = [url 'session'];
   
    data = ['user[email]=',user,'&user[password]=',password];
    options = weboptions;
    options.Timeout=20;
    response = webwrite(sessionURL,data,options);
    %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
    % NEED SOME ERROR HANDLING 
    %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
    
    
    token=response.data.token;
    
end
        if algo1==1
        algorithm_id1=17;% OPTIMUS 1
        else
        algorithm_id1=14;% MINO 1    
        end
        
        algorithm_id=num2str(algorithm_id1);
        signalURL = [url 'algorithms/' algorithm_id '/signals?after=2019-02-10'];
       % data = struct('signals',signals);
        options = weboptions('MediaType','application/json','HeaderFields',{'Authorization',token},'CertificateFilename','');
        options.Timeout=20;
        response = webread(signalURL,options);
        %response.data.signals.price;
        %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
        
        
        clear Price
        clear PriceR
        clear SideR
        clear TimeStampR
        clear StockR
        
        k1=1;
        rg1=1
        
        for i=1:21*17*2+2% needs to be odd
            Price(i)=response.data.signals(i).price;
            Side1=response.data.signals(i).side;
            timestamp1=response.data.signals(i).timestamp;
            Symbol1=response.data.signals(i).symbol;
            
            if strcmp(Side1,'buy')==1
                SideR(k1)=1;
                PriceR(k1)=Price(i);
                StockR{k1}=Symbol1;
                TimeStampR{k1}=timestamp1;              
                k1=k1+1;
            elseif strcmp(Side1,'sell')==1
                SideR(k1)=2;
                PriceR(k1)=Price(i);
                StockR{k1}=Symbol1;
                TimeStampR{k1}=timestamp1;
                k1=k1+1;
            elseif strcmp(Side1,'hold')==1
                SideR(k1)=3;
                SideR(k1+1)=3;
                PriceR(k1)=Price(i);
                PriceR(k1+1)=Price(i);
                StockR{k1}=Symbol1;
                StockR{k1+1}=Symbol1;
                TimeStampR{k1}=timestamp1;
                TimeStampR{k1+1}=timestamp1;
                k1=k1+2;
            end
                  
            rg1=rg1+1;
        end
        
        %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
        
        LR=length(PriceR);
        
        if mod(LR,2)==0
        PriceA1=PriceR(2:end-1);
        SideA1=SideR(2:end-1);
        StockA1=StockR(2:end-1);
        TimeStampA1=TimeStampR(2:end-1);
        else        
        PriceA1=PriceR(2:end);
        SideA1=SideR(2:end);
        StockA1=StockR(2:end);
        TimeStampA1=TimeStampR(2:end);
        end
        
        x1=length(PriceA1):-1:1;
        
        PriceB=PriceA1(x1);
        SideB=SideA1(x1);
        StockB=StockA1(x1);
        TimeStampB=TimeStampA1(x1);
        
        %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
        sz1=floor( length(PriceB ));
        odd1=1:2:sz1;
        even1=2:2:sz1;
        %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
        % BUY AND SELL
        %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
        sell=PriceB(even1);
        buy=PriceB(odd1);
        %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
        SideBuy=SideB(odd1);
        
        GainP=sell./buy;
        short1=find(SideBuy==2);
        GainP1=GainP;
        GainP1(short1)=2-GainP1(short1);
        
        L2=21*17;% 3 months trading 
    
        clear timestamps
        clear Stock
        clear PriceG
        clear SideG
        clear times
        
        k1=1;
        for i=1:length(PriceA1)
        timestamps{i}=response.data.signals(i+1).timestamp;    
        Stock{i}=response.data.signals(i+1).symbol;    
        PriceG(i)=response.data.signals(i+1).price;   
        SideG{i}=response.data.signals(i+1).side; 
        end
    
       
        T = table(Stock',PriceG',SideG',timestamps');
        filename = 'OptimusInfo2.xlsx';
        Folder1='C:/DataAlphaHubReader/';
        file1=[Folder1 filename];
        if ~exist(Folder1, 'dir')
            mkdir(Folder1)
        end
        writetable(T,file1,'Sheet',1,'Range','D1');
        
        TimeStampB1=TimeStampB(odd1);
        times1=TimeStampB1(end-L2+1:end);
        clear Time1
        for i=1:length(times1)
        tR=char(times1{i});
        Time1(i,:)=tR(1:10);        
        end
        
        %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
  
        
        %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
        %DATA FOR TODAY
        %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
        OpenA=response.data.signals(1).symbol;
        OpenPriceA=response.data.signals(1).price;
        OpenSideA=response.data.signals(1).side;
        CloseA=response.data.signals(2).symbol;
        ClosePriceA=response.data.signals(2).price;
        CloseSideA=response.data.signals(2).side;
        Time=response.data.signals(1).timestamp;
        Time1=Time(1:10);
        DateOpen1=Time1;

end

